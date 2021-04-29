import cv2
import numpy as np
import socket
import sys
import pickle
import struct

frame = np.random.randint(255, size=(900,800,3),dtype=np.uint8)


TCP_IP = 'localhost'
TCP_PORT = 8001

sock = socket.socket()
sock.connect((TCP_IP, TCP_PORT))

encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
result, imgencode = cv2.imencode('.jpg', frame, encode_param)
data = np.array(imgencode)
stringData = data.tostring()
send1 = str(len(stringData)).ljust(16)
print(send1)
sock.send(send1.encode("utf-8"));
sock.send( stringData );
sock.close()

#decimg=cv2.imdecode(data,1)
#cv2.imshow('CLIENT',decimg)
#cv2.waitKey(0)
#cv2.destroyAllWindows()
