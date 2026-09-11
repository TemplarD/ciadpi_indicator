# ciadpi_snimod — движок №3 (SNI case-mod)
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra
PKG ?= pkg-config
BIN = bin/ciadpi_snimod

all: $(BIN)

$(BIN): ciadpi_snimod.c
	@mkdir -p bin
	$(CC) $(CFLAGS) $(shell $(PKG) --cflags libnetfilter_queue) \
	    -o $@ $< $(shell $(PKG) --libs libnetfilter_queue)

clean:
	rm -rf bin

.PHONY: all clean
