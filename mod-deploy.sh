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

ssh ${TARGET} mount / -o remount,rw

ssh ${TARGET} rm -rf /usr/share/mod/html/css
ssh ${TARGET} rm -rf /usr/share/mod/html/js
ssh ${TARGET} mkdir -p /usr/share/mod/html/css/fontello/{css,font} /usr/share/mod/html/js/{lib/slick/fonts,utils}

ssh ${TARGET} rm -f  /usr/lib/python3.4/site-packages/mod/*.py*
ssh ${TARGET} rm -f  /usr/lib/python3.4/site-packages/mod/communication/*.py*
ssh ${TARGET} rm -f  /usr/lib/python3.4/site-packages/modtools/*.py*

scp html/*.html                   ${TARGET}:/usr/share/mod/html/
scp html/include/*.html           ${TARGET}:/usr/share/mod/html/include/
scp html/resources/*.html         ${TARGET}:/usr/share/mod/html/resources/
scp html/css/*.css                ${TARGET}:/usr/share/mod/html/css/
scp html/css/fontello/css/*.css   ${TARGET}:/usr/share/mod/html/css/fontello/css/
scp html/css/fontello/font/*.*    ${TARGET}:/usr/share/mod/html/css/fontello/font/
scp html/js/*.js                  ${TARGET}:/usr/share/mod/html/js/
scp html/js/lib/*.js              ${TARGET}:/usr/share/mod/html/js/lib/
scp html/js/lib/slick/*.{css,gif} ${TARGET}:/usr/share/mod/html/js/lib/slick/
scp html/js/lib/slick/*min.js     ${TARGET}:/usr/share/mod/html/js/lib/slick/
scp html/js/lib/slick/fonts/*.*   ${TARGET}:/usr/share/mod/html/js/lib/slick/fonts/
scp html/js/utils/*.js            ${TARGET}:/usr/share/mod/html/js/utils/
scp html/img/*.png                ${TARGET}:/usr/share/mod/html/img/
scp mod/*.py                      ${TARGET}:/usr/lib/python3.4/site-packages/mod/
scp mod/communication/*.py        ${TARGET}:/usr/lib/python3.4/site-packages/mod/communication/
scp modtools/*.py                 ${TARGET}:/usr/lib/python3.4/site-packages/modtools/

ssh ${TARGET} rm -rf /usr/lib/python3.4/site-packages/mod/__pycache__
ssh ${TARGET} rm -rf /usr/lib/python3.4/site-packages/mod/communication/__pycache__
ssh ${TARGET} rm -rf /usr/lib/python3.4/site-packages/modtools/__pycache__

echo "all ok"
