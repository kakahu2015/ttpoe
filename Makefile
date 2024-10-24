# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright (c) 2023 Tesla Inc. All rights reserved.
#
# Makefile for the Tesla Transport Protocol (TTP) Kernel Module
#
# Authors:    Diwakar Tundlam <dntundlam@tesla.com>
#
# This software is licensed under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation, and may be copied, distributed, and
# modified under those terms.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; Without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

PWD  ?= $(pwd)
KVER ?= $(shell uname -r)
KDIR ?= /lib/modules/$(KVER)/build

all:: include/ver.h
	make -C $(KDIR) M=$(PWD) modules

clean::
	-make -C $(KDIR) M=$(PWD) clean
	-rm -f include/ver.h modttpoe/Module.symvers modttpip/Module.symvers

install:: all
	make /mnt/mac/modttpoe.ko /mnt/mac/modttpip.ko /mnt/mac/tests/.timestamp

/mnt/mac/modttpoe.ko: all
	-sudo cp modttpoe/modttpoe.ko /mnt/mac/modttpoe-$(KVER).ko
	-sudo ln -sf /mnt/mac/modttpoe-$(KVER).ko /mnt/mac/modttpoe.ko

/mnt/mac/modttpip.ko: all
	-sudo cp modttpip/modttpip.ko /mnt/mac/modttpip-$(KVER).ko
	-sudo ln -sf /mnt/mac/modttpip-$(KVER).ko /mnt/mac/modttpip.ko

/mnt/mac/tests/.timestamp: /mnt/mac/modttpoe.ko /mnt/mac/modttpip.ko
	-sudo cp -r tests /mnt/mac
	-sudo su -c "touch /mnt/mac/tests/.timestamp"

.PHONY: /mnt/mac/tests/.timestamp /mnt/mac/modttpoe.ko /mnt/mac/modttpip.ko

# Pass env VER="1.0" from command line for official builds
VER ?= "eng"

include/ver.h: Makefile
	@echo "/* Autogenerated file. PLEASE DO NOT EDIT */"                                > $(PWD)/$@
	@echo                                                                              >> $(PWD)/$@
	@echo "#define TTP_KERNEL_VERSION   \"$(KVER)\""                                   >> $(PWD)/$@
	@echo "#define TTP_STR(ss)          #ss"                                           >> $(PWD)/$@
	@echo "#define TTP_MKSTR(ss)        TTP_STR(ss)"                                   >> $(PWD)/$@
	@echo "#define AUTO_MODTTP_VERSION  TTP_BUILD_BASE \".\" TTP_MKSTR(TTP_BUILD_NUM)" >> $(PWD)/$@
	@echo                                                                              >> $(PWD)/$@
	@date -u +\#define\ TTP_BUILD_BASE\ \ \ \"$(VER)0.%y%m\"                           >> $(PWD)/$@
	@echo -n "#define TTP_BUILD_NUM     "                                              >> $(PWD)/$@
	@git log --oneline --since='\$\(date\ \-u\ \+\"\%m/1/\%Y\"\)' | wc -l              >> $(PWD)/$@
	@echo                                                                              >> $(PWD)/$@
	@echo "/* Hint: const char *const ttp_version_string = AUTO_MODTTP_VERSION; */"    >> $(PWD)/$@
	@echo "extern const char *const ttp_version_string;"                               >> $(PWD)/$@
