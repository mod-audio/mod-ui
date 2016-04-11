#!/bin/bash

set -e

YEAR=$(date +%Y)
VERSION="0.7.0+"

SRC="lunr.js utils.js event_emitter.js tokenizer.js pipeline.js vector.js sorted_set.js index.js document_store.js token_store.js"

cat wrapper_start $SRC wrapper_end \
    | sed "s/@YEAR/${YEAR}/" \
    | sed "s/@VERSION/${VERSION}/" > ../lunr.js
