echo ':: Installing python dependencies'
python3 -m venv modui-env
source modui-env/bin/activate
pip3 install -r requirements.txt

echo ':: Compiling c utils'
make -C utils

echo ':: Starting server'
python3 ./server.py
