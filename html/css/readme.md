## LESS compiler for MOD-UI's css

NodeJS and its package manager npm are required to install the dependencies,
which are included in package.json. Once you have them installed, simply run: 

```shell
sudo npm install
```

On some systems it's required to install grunt-cli, too:

```shell 
sudo npm install -g grunt-cli
```

It might happen that the sudo command installs the hidden directory ".npm"
not into your users home directory but in /root. If so, just move the folder
over to your users home directory and make sure its content and the folder
itself belong to your user:

```shell
sudo mv /root.npm ~/
sudo chown -R $USER:$USER ~/.npm
```

On some systems the binary of "nodejs" is called "node". In this case add
a link to it:

```shell 
sudo ln -s /usr/bin/nodejs /usr/bin/node
```

If everything is set up correctly you should have a working grunt. To use it
switch over to the directory this readme is located and run "grunt" in a
terminal.

It should watch every .less and .css file inside the less folder and compile
into main.css. Ideally, every section should have its .less file. Bootstrap
is included in main.less.
