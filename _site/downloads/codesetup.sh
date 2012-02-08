#!/bin/bash

#
# Script name: setup_codesourcery.sh
# Version: 2.1 - 2011-09-19
#
# Copyright (C) 2009-2011  Matthias "Maddes" Buecher
#

#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# http://www.gnu.org/licenses/gpl-2.0.txt
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#


##
## Script Functions
##
function install_toolchain()
{
	BINPATH="${INSTALLPATH}/${VERSION}/bin"
	SCRIPTFILE="${SCRIPTPATH}/${SCRIPTPREFIX}${VERSION}.sh"

	echo "Installing ${VERSION}:"

#	# Download toolchain
	[ ! -d "${DLDIR}" ] && mkdir -p "${DLDIR}"
	wget -N -P "${DLDIR}" "${DLBASEPATH}/${CCPREFIX}/${DLFILE}"

#	# Install toolchain (by extracting)
	echo "Extracting..."
	[ ! -d "${INSTALLPATH}" ] && mkdir -p "${INSTALLPATH}"
	tar -x --bzip2 -f "${DLDIR}"/"${DLFILE}" -C "${INSTALLPATH}"

#	# Create toolchain environment script
	echo "Creating script file ${SCRIPTFILE} ..."
	cat >"${SCRIPTFILE}" << __EOF
#!/bin/bash
echo "Type 'exit' to return to non-crosscompile environment"
[ -n "\${CROSS_COMPILE}" ] && { echo "ALREADY in crosscompile environment for \${ARCH} (\${CROSS_COMPILE})"; exit; }
export PATH='${BINPATH}':\${PATH}
export ARCH='${ARCHCODE}'
export CROSS_COMPILE='${CCPREFIX}-'
echo "NOW in crosscompile environment for \${ARCH} (\${CROSS_COMPILE})"
/bin/bash
echo 'Back in non-crosscompile environment'
__EOF
	[ ! -x "${SCRIPTFILE}" ] && chmod +x "${SCRIPTFILE}"

	echo "Done."
}


###
### Install prerequisites
###

[ "`whoami`" != "root" ] && {
	echo "$0: ABORT!!! Only for root user"
	exit 1
}

# --> general buildtools & development packages
#     wget & bzip2 for downloading and unpacking
#     uboot's mkimage & devio for creating uImage
echo "Installing prerequisites:"
PACKAGES='build-essential linux-libc-dev wget bzip2 uboot-mkimage devio ncurses-dev'
DOINSTALL=0
for PACKAGE in ${PACKAGES}
 do
#	# special cases
	[ "${PACKAGE}" = "ncurses-dev" ] && PACKAGE="libncurses5-dev" ; # package ncurses-dev is virtual on Debian, which can not be found via dpkg

	dpkg -l | grep -q -F -e "${PACKAGE}"
	DOINSTALL=$?
	[ "${DOINSTALL}" -ne 0 ] && break
done
[ "${DOINSTALL}" -ne 0 ] && {
	aptitude update
	aptitude install ${PACKAGES}
}


###
### Install toolchains
###


### Mentor Graphics' (ex-CodeSourcery) toolchains
###   http://www.mentor.com/embedded-software/sourcery-tools/sourcery-codebench/lite-edition
###   (navigation: Products --> Embedded Software --> Sourcery Tools --> Sourcery CodeBench --> Editions --> Lite Edition Download)
#
###  before 2011:
###   http://www.codesourcery.com/sgpp/lite_edition.html
###   (navigation: Products --> Sourcery G++ --> Editions --> Lite)
#
### Note: the toolchains for the different targets can be installed in parallel

## Pathes for toolchains, scripts and downloads
INSTALLPATH='/usr/local/codesourcery'
SCRIPTPATH='/usr/local/bin'
SCRIPTPREFIX='codesourcery-'
DLDIR="/root/work/codesourcery"
#
DLBASEPATH='https://sourcery.mentor.com/public/gnu_toolchain/'
# before 2011: DLBASEPATH='http://www.codesourcery.com/public/gnu_toolchain/'

## -> ARM GNU/Linux target
ARCHCODE='arm'
CCPREFIX='arm-none-linux-gnueabi'
## (arm-20011.03)
VERSION='arm-2011.03'
DLFILE='arm-2011.03-41-arm-none-linux-gnueabi-i686-pc-linux-gnu.tar.bz2'
#install_toolchain
## (arm-2009q3)
VERSION='arm-2009q3'
DLFILE='arm-2009q3-67-arm-none-linux-gnueabi-i686-pc-linux-gnu.tar.bz2'
install_toolchain
## (arm-2009q1)
VERSION='arm-2009q1'
DLFILE='arm-2009q1-203-arm-none-linux-gnueabi-i686-pc-linux-gnu.tar.bz2'
#install_toolchain

## -> MIPS GNU/Linux target
ARCHCODE='mips'
CCPREFIX='mips-linux-gnu'
## (mips-4.4)
VERSION='mips-4.4'
DLFILE='mips-4.4-57-mips-linux-gnu-i686-pc-linux-gnu.tar.bz2'
#install_toolchain
