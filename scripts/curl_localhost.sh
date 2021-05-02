while [ 1 ]
do
	curl localhost:5000/video_feed >  /dev/null 2>&1
done
