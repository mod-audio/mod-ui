#!/bin/bash

set -e

cd $(dirname ${0})

if ping -c 1 -W 0.05 192.168.51.1 > /dev/null; then
  TARGET=root@192.168.51.1
elif ping -c 1 -W 0.2 moddwarf.local > /dev/null; then
  TARGET=root@moddwarf.local
elif ping -c 1 -W 0.2 modduox.local > /dev/null; then
  TARGET=root@modduox.local
elif ping -c 1 -W 0.2 modduo.local > /dev/null; then
  TARGET=root@modduo.local
else
  echo "not connected"
  exit 1
fi

# needed since ssh rsa deprecation/breakage
SSH_OPTIONS="-o PubkeyAcceptedAlgorithms=+ssh-rsa"
SCP_OPTIONS="${SSH_OPTIONS} -O"

ssh ${SSH_OPTIONS} ${TARGET} mount / -o remount,rw

ssh ${SSH_OPTIONS} ${TARGET} rm -rf /usr/share/mod/html/css
ssh ${SSH_OPTIONS} ${TARGET} rm -rf /usr/share/mod/html/js
ssh ${SSH_OPTIONS} ${TARGET} mkdir -p /usr/share/mod/html/css/fontello/{css,font} /usr/share/mod/html/js/{lib/slick/fonts,utils}

ssh ${SSH_OPTIONS} ${TARGET} rm -f  /usr/lib/python3.4/site-packages/mod/*.py*
ssh ${SSH_OPTIONS} ${TARGET} rm -f  /usr/lib/python3.4/site-packages/mod/communication/*.py*
ssh ${SSH_OPTIONS} ${TARGET} rm -f  /usr/lib/python3.4/site-packages/modtools/*.py*

scp ${SCP_OPTIONS} html/*.html                   ${TARGET}:/usr/share/mod/html/
scp ${SCP_OPTIONS} html/include/*.html           ${TARGET}:/usr/share/mod/html/include/
scp ${SCP_OPTIONS} html/resources/*.html         ${TARGET}:/usr/share/mod/html/resources/
scp ${SCP_OPTIONS} html/css/*.css                ${TARGET}:/usr/share/mod/html/css/
scp ${SCP_OPTIONS} html/css/fontello/css/*.css   ${TARGET}:/usr/share/mod/html/css/fontello/css/
scp ${SCP_OPTIONS} html/css/fontello/font/*.*    ${TARGET}:/usr/share/mod/html/css/fontello/font/
scp ${SCP_OPTIONS} html/js/*.js                  ${TARGET}:/usr/share/mod/html/js/
scp ${SCP_OPTIONS} html/js/lib/*.js              ${TARGET}:/usr/share/mod/html/js/lib/
scp ${SCP_OPTIONS} html/js/lib/slick/*.{css,gif} ${TARGET}:/usr/share/mod/html/js/lib/slick/
scp ${SCP_OPTIONS} html/js/lib/slick/*min.js     ${TARGET}:/usr/share/mod/html/js/lib/slick/
scp ${SCP_OPTIONS} html/js/lib/slick/fonts/*.*   ${TARGET}:/usr/share/mod/html/js/lib/slick/fonts/
scp ${SCP_OPTIONS} html/js/utils/*.js            ${TARGET}:/usr/share/mod/html/js/utils/
scp ${SCP_OPTIONS} html/img/*.png                ${TARGET}:/usr/share/mod/html/img/
scp ${SCP_OPTIONS} html/img/*.svg                ${TARGET}:/usr/share/mod/html/img/
scp ${SCP_OPTIONS} mod/*.py                      ${TARGET}:/usr/lib/python3.4/site-packages/mod/
scp ${SCP_OPTIONS} mod/communication/*.py        ${TARGET}:/usr/lib/python3.4/site-packages/mod/communication/
scp ${SCP_OPTIONS} modtools/*.py                 ${TARGET}:/usr/lib/python3.4/site-packages/modtools/

ssh ${SSH_OPTIONS} ${TARGET} rm -rf /usr/lib/python3.4/site-packages/mod/__pycache__
ssh ${SSH_OPTIONS} ${TARGET} rm -rf /usr/lib/python3.4/site-packages/mod/communication/__pycache__
ssh ${SSH_OPTIONS} ${TARGET} rm -rf /usr/lib/python3.4/site-packages/modtools/__pycache__

echo "all ok"
