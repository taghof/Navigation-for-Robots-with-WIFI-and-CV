#!/bin/bash

FILES=*
THUMBDIR=./thumbs
if [ ! -d "$THUMBDIR" ]; then
	mkdir ./thumbs
fi

for i in $FILES
do
echo "Prcoessing image $i ..."
/usr/bin/convert -thumbnail 150 $i $THUMBDIR/$i
done
