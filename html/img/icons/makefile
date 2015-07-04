PNG = $(wildcard *.png)
FILE="icons.css"

all:
	@-rm icons.css
	@touch icons.css
	@for i in $(PNG) ; do \
		io=$$(echo $$i | sed 's/.png//') ; \
		convert $$i -negate black/$$i ; \
		mv $$i white/$$i ; \
	done
	@for i in white/*.png ; do \
		io=$$(echo $$i | sed 's/.png//' | sed 's/white\///') ; \
		if=$$(echo $$i | sed 's/white\///') ; \
		echo ".mod-dark  .mod-icon-"$$io", .mod-light.mod-icon-"$$io" {\n    background-image: url(white/"$$if");\n}" >> $(FILE) ; \
		echo ".mod-light .mod-icon-"$$io", .mod-dark.mod-icon-"$$io"  {\n    background-image: url(black/"$$if");\n}\n\n" >> $(FILE) ; \
	done
