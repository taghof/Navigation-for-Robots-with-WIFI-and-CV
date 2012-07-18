#! /bin/busybox ash
echo "killing program.elf"
killall program.elf



echo "setting pin 127"
gpio 127 -d ho 1
sleep 1
gpio 127 -d i
sleep 1
echo "exporting LD_PRELOAD"
export LD_PRELOAD=/data/video/libioctl_arm.so

echo "inserting modules"
echo "1:"
insmod /data/video/nls_base.ko
#sleep 1
echo "2:"
insmod /data/video/nls_cp437.ko
#sleep 1
echo "3:"
insmod /data/video/nls_iso8859-1.ko
#sleep 1
echo "4:"
insmod /data/video/nls_utf8.ko
#sleep 1
echo "5:"
insmod /data/video/fat.ko
#sleep 1
echo "6:"
insmod /data/video/vfat.ko
#sleep 1
echo "7:"
insmod /data/video/sd_mod.ko
#sleep 1
echo "8:"
insmod /data/video/scsi_wait_scan.ko
#sleep 1
echo "9:"
insmod /data/video/mac80211.ko
#insmod /data/video/block/nbd.ko
#sleep 1
echo "10:"
insmod /data/video/ex_rt3370sta.ko
#sleep 1
echo "11:"
- load.sh 1/73 1%
