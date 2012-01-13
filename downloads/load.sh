#! /bin/busybox ash

echo "setting pin 127"
gpio 127 -d ho 1
gpio 127 -d i

echo "copying newest modules"
cp /data/video/*.ko /custom_modules/

echo "loading nls_base.ko"
insmod /custom_modules/nls_base.ko
echo "loading nls_utf8.ko"
insmod /custom_modules/nls_utf8.ko
echo "loading nls_cp437.ko"
insmod /custom_modules/nls_cp437.ko
echo "loading nls_iso8859-1.ko"
insmod /custom_modules/nls_iso8859-1.ko
echo "loading sd_mod.ko"               
insmod /custom_modules/sd_mod.ko
echo "loading nbd.ko"
insmod /custom_modules/nbd.ko
echo "loading fat.ko"
insmod /custom_modules/fat.ko
echo "loading vfat.ko"
insmod /custom_modules/vfat.ko
#echo "inserting usbserial.ko"
#insmod /custom_modules/usbserial.ko
echo "loading dwc_otg.ko"
insmod /custom_modules/dwc_otg.ko
 
echo "waiting 5 secs..."
sleep 5
 
echo "displaying last lines of dmesg: "
echo "------------------------------- "

dmesg | tail