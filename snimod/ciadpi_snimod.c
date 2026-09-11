/* ciadpi_snimod v1.0 — третий движок обхода DPI (ciadpi_indicator).
 *
 * Идея (наша, не реализованная ни в byedpi, ни в zapret/nfqws):
 * DPI провайдера ищет подстроку "www.youtube.com" (lowercase) в SNI
 * TLS ClientHello и роняет соединение; фильтр РЕГИСТРОЗАВИСИМ —
 * SNI "WWW.YOUTUBE.COM" проходит (TLS handshake + HTTP 200 PoC),
 * серверу регистр безразличен (RFC 6066, server_name case-insensitive).
 * byedpi/nfqws не умеют править байты самого SNI. Этот демон
 * перехватывает исходящие ClientHello через NFQUEUE (qnum 210,
 * таблица nft inet ciadpi_snimod — генерит менеджер) и поднимает
 * регистр SNI у хостов из списка. Verdict всегда NF_ACCEPT.
 *
 * Сборка: make  →  bin/ciadpi_snimod
 * Аргументы: --qnum=N --hosts=файл [--debug] [--daemon]
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <linux/netfilter.h>          /* NF_ACCEPT */
#include <libnetfilter_queue/libnetfilter_queue.h>

#define DEFAULT_QNUM 210
#define MAX_HOSTS 512
#define HOST_LEN 253

static volatile sig_atomic_t g_stop = 0;
static int g_qnum = DEFAULT_QNUM;
static int g_debug = 0;

static char g_hosts[MAX_HOSTS][HOST_LEN + 1];
static int g_nhosts = 0;

static void on_sig(int sig) { (void)sig; g_stop = 1; }

static void usage(void) {
    fprintf(stderr,
        "ciadpi_snimod — SNI case-mod engine (ciadpi_indicator #3)\n"
        "Usage: ciadpi_snimod [--qnum=N] [--hosts=file] [--debug] [--daemon]\n"
        "  --qnum=N   NFQUEUE number (default %d)\n"
        "  --hosts=f  hosts file, one lowercase host per line\n"
        "  --debug    log decisions to stdout\n"
        "  --daemon   fork to background\n",
        DEFAULT_QNUM);
    exit(1);
}

/* ---------- чексуммы ---------- */
static unsigned short in_csum(const unsigned char *data, int len) {
    unsigned int sum = 0;
    for (int i = 0; i < len; i += 2) {
        unsigned int w = ((unsigned int)data[i]) << 8;
        if (i + 1 < len) w |= data[i + 1];
        sum += w;
    }
    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    return (unsigned short)(~sum);
}

static void fix_csums(unsigned char *pkt, int len, int ihl) {
    struct iphdr *ip = (struct iphdr *)pkt;
    struct tcphdr *tcp = (struct tcphdr *)(pkt + ihl);
    int tcp_seg_len = len - ihl;
    /* TCP pseudo-header checksum */
    unsigned int sum = 0;
    unsigned int src = ntohl(ip->saddr), dst = ntohl(ip->daddr);
    sum += (src >> 16) & 0xFFFF; sum += src & 0xFFFF;
    sum += (dst >> 16) & 0xFFFF; sum += dst & 0xFFFF;
    sum += htons(IPPROTO_TCP);
    sum += htons((unsigned short)tcp_seg_len);
    /* сумма сегмента */
    const unsigned char *t = (const unsigned char *)tcp;
    for (int i = 0; i < tcp_seg_len; i += 2) {
        unsigned int w = ((unsigned int)t[i]) << 8;
        if (i + 1 < tcp_seg_len) w |= t[i + 1];
        sum += w;
    }
    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    ip->check = 0;
    ip->check = in_csum((const unsigned char *)ip, ihl);
    tcp->check = 0;
    tcp->check = (unsigned short)(~sum);
}

/* ---------- поиск SNI в TLS ClientHello ----------
 * Возвращает 1 и заполняет sni/sni_len, если в пейлоаде — полный
 * ClientHello с SNI. Частичные (сплит) сегменты не трогаем —
 * их редактировать опасно без реассемблинга. */
static int find_sni(const unsigned char *p, int plen,
                    const unsigned char **sni_out, int *sni_len_out) {
    if (plen < 43) return 0;
    if (!(p[0] == 0x16 && p[1] == 0x03 && p[5] == 0x01)) return 0;
    int hs_len = (p[6] << 16) | (p[7] << 8) | p[8];
    if (hs_len < 38 || 9 + hs_len > plen) return 0;   /* не полный CH */
    const unsigned char *hs = p + 9;
    int off = 34;                                      /* ver(2)+random(32) */
    if (off + 1 > hs_len) return 0;
    off += 1 + hs[off];                                /* session id */
    if (off + 2 > hs_len) return 0;
    off += 2 + ((hs[off] << 8) | hs[off + 1]);         /* cipher suites */
    if (off + 1 > hs_len) return 0;
    off += 1 + hs[off];                                /* compression */
    if (off + 2 > hs_len) return 0;
    int ext_len = (hs[off] << 8) | hs[off + 1];
    off += 2;
    if (off + ext_len > hs_len) return 0;
    const unsigned char *ext = hs + off;
    int eoff = 0;
    while (eoff + 4 <= ext_len) {
        int etype = (ext[eoff] << 8) | ext[eoff + 1];
        int elen  = (ext[eoff + 2] << 8) | ext[eoff + 3];
        if (eoff + 4 + elen > ext_len) break;          /* битая запись */
        if (etype == 0 && elen >= 5) {                  /* server_name */
            if (ext[eoff + 4] == 0x00) {                /* type host_name */
                int name_len = (ext[eoff + 5] << 8) | ext[eoff + 6];
                if (name_len > 0 && 7 + name_len <= elen) {
                    *sni_out = ext + eoff + 7;
                    *sni_len_out = name_len;
                    return 1;
                }
            }
        }
        eoff += 4 + elen;
    }
    return 0;
}

/* ---------- NFQUEUE callback ---------- */
static int cb(struct nfq_q_handle *qh, struct nfgenmsg *nfmsg,
             struct nfq_data *nfa, void *data) {
    (void)nfmsg; (void)data;
    struct nfqnl_msg_packet_hdr *ph = nfq_get_msg_packet_hdr(nfa);
    if (!ph) return nfq_set_verdict(qh, 0, NF_ACCEPT, 0, NULL);
    int id = ntohl(ph->packet_id);
    unsigned char *pkt = NULL;
    int len = nfq_get_payload(nfa, &pkt);
    if (len >= 40 && pkt) {
        struct iphdr *ip = (struct iphdr *)pkt;
        if (ip->version == 4 && ip->protocol == IPPROTO_TCP) {
            int ihl = ip->ihl * 4;
            if (ihl >= 20 && len >= ihl + 20) {
                struct tcphdr *tcp = (struct tcphdr *)(pkt + ihl);
                int thl = tcp->doff * 4;
                if (thl >= 20 && len > ihl + thl) {
                    const unsigned char *pl = pkt + ihl + thl;
                    int plen = len - ihl - thl;
                    const unsigned char *sni; int sni_len;
                    if (find_sni(pl, plen, &sni, &sni_len)) {
                        for (int i = 0; i < g_nhosts; i++) {
                            int hl = (int)strlen(g_hosts[i]);
                            if (hl != sni_len) continue;
                            int match = 1;
                            for (int j = 0; j < hl; j++) {
                                unsigned char c = sni[j];
                                if (c >= 'A' && c <= 'Z') c += 32;
                                if (c != (unsigned char)g_hosts[i][j]) {
                                    match = 0; break;
                                }
                            }
                            if (!match) continue;
                            /* поднимаем регистр SNI-строки */
                            for (int j = 0; j < sni_len; j++) {
                                unsigned char c = ((unsigned char *)sni)[j];
                                if (c >= 'a' && c <= 'z')
                                    ((unsigned char *)sni)[j] =
                                        (unsigned char)(c - 32);
                            }
                            fix_csums(pkt, len, ihl);
                            if (g_debug)
                                printf("snimod: uppercased SNI len=%d\n",
                                       sni_len);
                            break;
                        }
                    }
                }
            }
        }
    }
    /* правили или нет — пакет всегда идёт дальше */
    return nfq_set_verdict(qh, id, NF_ACCEPT,
                           len > 0 ? 0 : 0, NULL);
}

static int load_hosts(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char line[512];
    while (fgets(line, sizeof(line), f) && g_nhosts < MAX_HOSTS) {
        char *s = line;
        while (*s == ' ' || *s == '\t') s++;
        char *e = s + strlen(s);
        while (e > s && (e[-1] == '\n' || e[-1] == '\r' ||
                         e[-1] == ' ' || e[-1] == '\t')) *--e = 0;
        if (*s == 0 || *s == '#') continue;
        if (strlen(s) > HOST_LEN) continue;
        /* храним lowercase */
        for (char *q = s; *q; q++)
            if (*q >= 'A' && *q <= 'Z') *q += 32;
        strncpy(g_hosts[g_nhosts], s, HOST_LEN);
        g_hosts[g_nhosts][HOST_LEN] = 0;
        g_nhosts++;
    }
    fclose(f);
    return g_nhosts;
}

int main(int argc, char **argv) {
    const char *hosts_file = NULL;
    int daemonize = 0;
    for (int i = 1; i < argc; i++) {
        if (!strncmp(argv[i], "--qnum=", 7)) g_qnum = atoi(argv[i] + 7);
        else if (!strncmp(argv[i], "--hosts=", 8)) hosts_file = argv[i] + 8;
        else if (!strcmp(argv[i], "--debug")) g_debug = 1;
        else if (!strcmp(argv[i], "--daemon")) daemonize = 1;
        else usage();
    }
    if (hosts_file) {
        int n = load_hosts(hosts_file);
        if (n < 0) {
            fprintf(stderr, "snimod: cannot open hosts file: %s\n",
                    hosts_file);
            return 2;
        }
        if (g_debug) printf("snimod: %d hosts loaded\n", n);
    } else {
        fprintf(stderr, "snimod: --hosts is required (nothing to do)\n");
        return 2;
    }
    if (daemonize) {
        pid_t pid = fork();
        if (pid < 0) { perror("fork"); return 3; }
        if (pid > 0) { printf("%d\n", pid); return 0; }
        setsid();
        close(0); close(1); close(2);
    }
    signal(SIGINT, on_sig);
    signal(SIGTERM, on_sig);

    struct nfq_handle *h = nfq_open();
    if (!h) { fprintf(stderr, "snimod: nfq_open error\n"); return 4; }
    nfq_unbind_pf(h, AF_INET);
    if (nfq_bind_pf(h, AF_INET) < 0) {
        fprintf(stderr, "snimod: nfq_bind_pf error\n"); return 5;
    }
    struct nfq_q_handle *qh = nfq_create_queue(h, g_qnum, cb, NULL);
    if (!qh) { fprintf(stderr, "snimod: nfq_create_queue(%d) error\n",
                       g_qnum); return 6; }
    if (nfq_set_mode(qh, NFQNL_COPY_PACKET, 0xFFFF) < 0) {
        fprintf(stderr, "snimod: nfq_set_mode error\n"); return 7;
    }
    int fd = nfq_fd(h);
    char buf[65536] __attribute__((aligned));
    while (!g_stop) {
        int rv = recv(fd, buf, sizeof(buf), 0);
        if (rv < 0) {
            if (errno == EINTR || errno == EAGAIN) continue;
            if (errno == ENOBUFS) { usleep(1000); continue; }
            perror("snimod: recv");
            break;
        }
        nfq_handle_packet(h, buf, rv);
    }
    nfq_destroy_queue(qh);
    nfq_close(h);
    if (g_debug) printf("snimod: bye\n");
    return 0;
}
