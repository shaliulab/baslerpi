#! /bin/bash

TEMPFILE=$(tempfile -s ".txt")
find $1 -name *.png | sort -g > $TEMPFILE

while read -r IMAGE;
do
IMG_TEMPFILE=$(tempfile -s "png" -p "TIMELAPSE_"$IMAGE)
DATETIME=$(stat -c %y $IMAGE  | cut -f 1 -d. | tr ":" "-" | tr " " "_")
echo $DATETIME
convert $IMAGE -pointsize 50 -font FreeMono -background Khaki label:$DATETIME +swap -gravity Center -append $IMG_TEMPFILE
done

ffmpeg -r 10 -i /tmp/TIMELAPSE_%6d.png%6s.png  -c:v mjpeg $2
