#! /bin/bash

#sudo apt-get install imagemagick-6.q16
#sudo apt-get install ffmpeg

TEMPFILE=$(tempfile -s ".txt")
find $1 -name *.png | sort -g > $TEMPFILE
echo $TEMPFILE

while read -r IMAGE;
do
echo $IMAGE
IMAGE_NAME=$(basename $IMAGE)
IMG_TEMPFILE=$(tempfile -s ".png" -p "TIMELAPSE_${IMAGE_NAME}")
echo $IMG_TEMPFILE
DATETIME=$(stat -c %y $IMAGE  | cut -f 1 -d. | tr ":" "-" | tr " " "_")
echo $DATETIME
convert $IMAGE -pointsize 50 -font FreeMono -background Khaki label:$DATETIME +swap -gravity Center -append $IMG_TEMPFILE || break
done < $TEMPFILE

ffmpeg -r 10 -pattern_type glob -i '/tmp/TIMELAPSE_*.png*.png' -c:v mjpeg $2
rm /tmp/TIMELAPSE*
