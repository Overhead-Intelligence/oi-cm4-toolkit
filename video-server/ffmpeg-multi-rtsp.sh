#!/bin/bash

# Forward RTSP stream 1
#ffmpeg -i rtsp://10.227.1.50:8554/main.264 -c copy -f rtsp rtsp://127.0.0.1:8554/cam1

# Forward RTSP stream 2
ffmpeg -i rtsp://10.224.1.150:30000/test -c copy -f rtsp rtsp://45.32.196.115:5554/jupiter

# Forward RTSP stream 3
#ffmpeg -rtsp_transport -i rtsp://192.168.1.102/stream3 -c copy -f rtsp rtsp://127.0.0.1:8554/cam3 &

