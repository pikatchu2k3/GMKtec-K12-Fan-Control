/*
 * k12-fan-helper.c — SUID-Root-Helper für GMKtec NucBox K12 EC Lüftersteuerung
 *
 * KEINE rohen Speicheradressen als Argumente. Nur abstrakte Kommandos.
 * EC-Base (0xFE0B0400) ist hardcodiert — ein Angreifer kann NUR Lüfter
 * und Modus umschalten, keinen beliebigen Speicher lesen/schreiben.
 *
 * Kommandos (Argumente):
 *   status            JSON mit Temperaturen, RPM, Mode
 *   mode <0|1|2>      Balanced(0) / Performance(1) / Silent(2)
 *   fan1 <0-100>      0=Auto, 1-100=manuell %
 *   fan2 <0-100>      0=Auto, 1-100=manuell %
 *   auto              Alles zurück auf Auto
 *
 * Build: gcc -O2 -s -o k12-fan-helper k12-fan-helper.c
 * SUID:  sudo chown root:root k12-fan-helper
 *        sudo chmod u+s k12-fan-helper
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <errno.h>

/* ---- EC Register Map (GMKtec K12 / ITE IT5570E) ---- */
#define EC_BASE         0xFE0B0400UL
#define EC_SIZE         0xFF

#define REG_FAN1_HI     0x35  /* Fan 1 RPM high byte */
#define REG_FAN1_LO     0x36  /* Fan 1 RPM low byte  */
#define REG_FAN2_HI     0x37  /* Fan 2 RPM high byte */
#define REG_FAN2_LO     0x38  /* Fan 2 RPM low byte  */
#define REG_CPU_TEMP    0x70  /* CPU temperature (°C) */
#define REG_GPU_TEMP    0x71  /* GPU temperature (°C) */
#define REG_MODE_CMD    0x32  /* Mode command register */
#define REG_FAN1_CTRL   0x33  /* Fan 1 control: 0=auto, 0x80|% = manual */
#define REG_FAN2_CTRL   0x34  /* Fan 2 control */

static volatile uint8_t *ec_map = NULL;
static int mem_fd = -1;

/* ---- EC Low-Level (protected) ---- */
static int ec_init(void)
{
    if (ec_map) return 1;

    mem_fd = open("/dev/mem", O_RDWR);
    if (mem_fd < 0) {
        fprintf(stderr, "{\"error\":\"Cannot open /dev/mem: %s\"}\n", strerror(errno));
        return 0;
    }

    /* mmap benötigt seitenweise Ausrichtung */
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) page_size = 4096;
    uint64_t page_aligned = EC_BASE & ~(uint64_t)(page_size - 1);
    uint64_t offset_in_page = EC_BASE - page_aligned;

    void *mapped = mmap(NULL, offset_in_page + EC_SIZE,
                        PROT_READ | PROT_WRITE, MAP_SHARED,
                        mem_fd, page_aligned);
    if (mapped == MAP_FAILED) {
        fprintf(stderr, "{\"error\":\"mmap EC failed (addr=0x%lx, page=0x%lx): %s\"}\n",
                (unsigned long)EC_BASE, (unsigned long)page_aligned, strerror(errno));
        close(mem_fd);
        mem_fd = -1;
        return 0;
    }
    ec_map = (volatile uint8_t *)mapped + offset_in_page;

    /* Nach erfolgreichem mmap: Root-Rechte abgeben.
     * Das Mapping bleibt auch ohne Root bestehen.
     * Falls setuid fehlschlägt (nicht root) → kein Problem. */
    if (geteuid() == 0) {
        if (setuid(getuid()) != 0) {
            /* silent – nicht kritisch, läuft halt als root weiter */
        }
    }

    return 1;
}

static void ec_close(void)
{
    if (ec_map) {
        /* ec_map zeigt auf die Seite + offset → original mmap-Start ermitteln */
        long page_size = sysconf(_SC_PAGESIZE);
        if (page_size <= 0) page_size = 4096;
        uint64_t page_aligned = EC_BASE & ~(uint64_t)(page_size - 1);
        uint64_t offset_in_page = EC_BASE - page_aligned;
        void *mapped_start = (void *)((uint8_t *)ec_map - offset_in_page);
        munmap(mapped_start, offset_in_page + EC_SIZE);
        ec_map = NULL;
    }
    if (mem_fd >= 0) {
        close(mem_fd);
        mem_fd = -1;
    }
}

static inline uint8_t ec_read(uint8_t reg)
{
    return ec_map[reg];
}

static inline void ec_write(uint8_t reg, uint8_t val)
{
    ec_map[reg] = val;
}

/* JSON-String escapen: " → \", \ → \\, \n → \\n, \t → \\t */
static void json_escape(const char *src, char *dst, size_t dst_size)
{
    size_t i = 0;
    while (*src && i + 6 < dst_size) {
        unsigned char c = (unsigned char)*src;
        switch (c) {
            case '"':  dst[i++] = '\\'; dst[i++] = '"';  break;
            case '\\': dst[i++] = '\\'; dst[i++] = '\\'; break;
            case '\n': dst[i++] = '\\'; dst[i++] = 'n';  break;
            case '\t': dst[i++] = '\\'; dst[i++] = 't';  break;
            case '\r': dst[i++] = '\\'; dst[i++] = 'r';  break;
            default:
                if (c < 0x20) {
                    /* nicht druckbare Steuerzeichen → \uXXXX */
                    if (i + 10 < dst_size) {
                        i += (size_t)snprintf(dst + i, dst_size - i, "\\u%04x", c);
                    }
                } else {
                    dst[i++] = c;
                }
                break;
        }
        src++;
    }
    dst[i] = '\0';
}

/* ---- Commands ---- */

static void cmd_status(void)
{
    if (!ec_init()) return;

    uint8_t f1h = ec_read(REG_FAN1_HI);
    uint8_t f1l = ec_read(REG_FAN1_LO);
    uint8_t f2h = ec_read(REG_FAN2_HI);
    uint8_t f2l = ec_read(REG_FAN2_LO);
    int fan1_rpm = (f1h << 8) | f1l;
    int fan2_rpm = (f2h << 8) | f2l;

    uint8_t cpu_temp = ec_read(REG_CPU_TEMP);
    uint8_t gpu_temp = ec_read(REG_GPU_TEMP);
    /* 0x31 = aktueller Modus (0=Balanced, 1=Performance, 2=Silent)
       0x32 = Schreibregister für Modus-Wechsel (0x80/0x81/0x82) */
    uint8_t mode_val = ec_read(0x31);
    uint8_t fan1_ctrl = ec_read(REG_FAN1_CTRL);
    uint8_t fan2_ctrl = ec_read(REG_FAN2_CTRL);

    int fan1_manual = (fan1_ctrl & 0x80) ? 1 : 0;
    int fan2_manual = (fan2_ctrl & 0x80) ? 1 : 0;
    int fan1_pct = fan1_ctrl & 0x7F;
    int fan2_pct = fan2_ctrl & 0x7F;

    const char *mode_str = "Unknown";
    int mode_code = (int)mode_val;
    switch (mode_val) {
        case 0: mode_str = "Balanced"; break;
        case 1: mode_str = "Performance"; break;
        case 2: mode_str = "Silent"; break;
        default: mode_code = -1; break;
    }

    printf("{"
        "\"cpu_temp\":%u,"
        "\"gpu_temp\":%u,"
        "\"fan1_rpm\":%d,"
        "\"fan2_rpm\":%d,"
        "\"mode\":\"%s\","
        "\"mode_code\":%d,"
        "\"fan1_pct\":%d,"
        "\"fan2_pct\":%d,"
        "\"fan1_manual\":%d,"
        "\"fan2_manual\":%d"
        "}\n",
        (unsigned)cpu_temp, (unsigned)gpu_temp,
        fan1_rpm, fan2_rpm,
        mode_str, mode_code,
        fan1_pct, fan2_pct,
        fan1_manual, fan2_manual
    );

    ec_close();
}

static void cmd_mode(int code)
{
    if (!ec_init()) return;

    uint8_t val;
    switch (code) {
        case 0: val = 0x80; break;  /* Balanced */
        case 1: val = 0x81; break;  /* Performance */
        case 2: val = 0x82; break;  /* Silent */
        default:
            fprintf(stderr, "{\"error\":\"Invalid mode: %d (0=Balanced, 1=Performance, 2=Silent)\"}\n", code);
            ec_close();
            return;
    }
    ec_write(REG_MODE_CMD, val);
    printf("{\"ok\":true,\"mode_code\":%d}\n", code);
    ec_close();
}

static int parse_int(const char *s, int min, int max, int *out)
{
    char *end = NULL;
    errno = 0;
    long val = strtol(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0' || val < (long)min || val > (long)max)
        return 0;
    *out = (int)val;
    return 1;
}

static void cmd_fan(int fan, int pct)
{
    if (!ec_init()) return;

    uint8_t reg = (fan == 1) ? REG_FAN1_CTRL : REG_FAN2_CTRL;

    if (pct <= 0) {
        ec_write(reg, 0x00);
        printf("{\"ok\":true,\"fan\":%d,\"mode\":\"auto\"}\n", fan);
    } else {
        ec_write(reg, 0x80 | (uint8_t)pct);
        printf("{\"ok\":true,\"fan\":%d,\"pct\":%d,\"mode\":\"manual\"}\n", fan, pct);
    }
    ec_close();
}

static void cmd_auto(void)
{
    if (!ec_init()) return;
    ec_write(REG_MODE_CMD, 0x80);   /* Balanced */
    ec_write(REG_FAN1_CTRL, 0x00);  /* Fan 1 auto */
    ec_write(REG_FAN2_CTRL, 0x00);  /* Fan 2 auto */
    printf("{\"ok\":true,\"action\":\"auto\",\"mode\":\"Balanced\",\"fan1\":\"auto\",\"fan2\":\"auto\"}\n");
    ec_close();
}

static void print_usage(void)
{
    printf("Usage: k12-fan-helper <command> [args]\n");
    printf("\n");
    printf("Commands:\n");
    printf("  status              Show temperatures, RPM, mode (JSON)\n");
    printf("  mode <0|1|2>        Set mode: 0=Balanced, 1=Performance, 2=Silent\n");
    printf("  fan1 <0-100>        Set fan 1 speed: 0=auto, 1-100=manual %%\n");
    printf("  fan2 <0-100>        Set fan 2 speed: 0=auto, 1-100=manual %%\n");
    printf("  auto                Restore automatic fan control\n");
}

int main(int argc, char *argv[])
{
    /* Buffer to avoid crash on minimal stdout buffer */
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    if (argc < 2) {
        print_usage();
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "status") == 0) {
        cmd_status();
    } else if (strcmp(cmd, "mode") == 0) {
        if (argc < 3) {
            fprintf(stderr, "{\"error\":\"Missing mode argument (0=Balanced, 1=Performance, 2=Silent)\"}\n");
            return 1;
        }
        int code;
        if (!parse_int(argv[2], 0, 2, &code)) {
            fprintf(stderr, "{\"error\":\"Invalid mode value: %s (0=Balanced, 1=Performance, 2=Silent)\"}\n", argv[2]);
            return 1;
        }
        cmd_mode(code);
    } else if (strcmp(cmd, "fan1") == 0) {
        if (argc < 3) {
            fprintf(stderr, "{\"error\":\"Missing percentage (0-100)\"}\n");
            return 1;
        }
        int pct;
        if (!parse_int(argv[2], 0, 100, &pct)) {
            fprintf(stderr, "{\"error\":\"Invalid fan value: %s (0=auto, 1-100=manual)\"}\n", argv[2]);
            return 1;
        }
        cmd_fan(1, pct);
    } else if (strcmp(cmd, "fan2") == 0) {
        if (argc < 3) {
            fprintf(stderr, "{\"error\":\"Missing percentage (0-100)\"}\n");
            return 1;
        }
        int pct;
        if (!parse_int(argv[2], 0, 100, &pct)) {
            fprintf(stderr, "{\"error\":\"Invalid fan value: %s (0=auto, 1-100=manual)\"}\n", argv[2]);
            return 1;
        }
        cmd_fan(2, pct);
    } else if (strcmp(cmd, "auto") == 0) {
        cmd_auto();
    } else if (strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0) {
        print_usage();
    } else {
        char escaped[128];
        json_escape(cmd, escaped, sizeof(escaped));
        fprintf(stderr, "{\"error\":\"Unknown command: %s\"}\n", escaped);
        return 1;
    }

    return 0;
}
