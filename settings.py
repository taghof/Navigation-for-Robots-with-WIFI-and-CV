#    Copyright (c) 2012 Morten Daugaard
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.

# Run settings

DEBUG = False
TEST = False#True
MULTI = False

# Constants

STOPPING = 0
INIT = 1
RUNNING = 2
PAUSED = 3
CAPTURE = 4

DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
MCAST_GRP = '224.1.1.1'

INITMSG = "\x01\x00\x00\x00"
INITMSG_MCAST = "\x02\x00\x00\x00"

TEST_DRONE_INIT_PORT = 5550 
WIFI_PORT = 5551
NAVDATA_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556


AUTOCONTROL = 0
JOYCONTROL = 1
