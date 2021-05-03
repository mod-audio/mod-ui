#!/bin/bash

cd /home/jan/MOD_Github_SW/mod-ui/

TARGET=root@192.168.51.1

ssh $TARGET mount / -o remount,rw

# ssh $TARGET rm -rf /usr/share/mod/html/css
# ssh $TARGET rm -rf /usr/share/mod/html/js
# ssh $TARGET mkdir -p /usr/share/mod/html/css/fontello/css /usr/share/mod/html/js/lib/slick

ssh $TARGET rm -f  /usr/lib/python3.4/site-packages/mod/*.py*
ssh $TARGET rm -f  /usr/lib/python3.4/site-packages/mod/communication/*.py*

scp html/*.html                 $TARGET:/usr/share/mod/html/
scp html/include/*.html         $TARGET:/usr/share/mod/html/include/
scp html/css/*.css              $TARGET:/usr/share/mod/html/css/
scp html/css/fontello/css/*.css $TARGET:/usr/share/mod/html/css/
scp html/js/*.js                $TARGET:/usr/share/mod/html/js/
scp html/js/lib/*.js            $TARGET:/usr/share/mod/html/js/lib/
scp html/js/lib/slick/*min.js   $TARGET:/usr/share/mod/html/js/lib/slick/
scp mod/*.py                    $TARGET:/usr/lib/python3.4/site-packages/mod/
scp mod/communication/*.py      $TARGET:/usr/lib/python3.4/site-packages/mod/communication/
scp modtools/*.py               $TARGET:/usr/lib/python3.4/site-packages/modtools/

ssh $TARGET rm -rf /usr/lib/python3.4/site-packages/mod/__pycache__
ssh $TARGET rm -rf /usr/lib/python3.4/site-packages/mod/communication/__pycache__

echo "all ok"