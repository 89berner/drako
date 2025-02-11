#!/bin/sh
 
DESTINATION_FOLDER="/home/near/Desktop/shr"
FOLDER_TO_SHARE="shr"
echo "[i] Mounting \\$FOLDER_TO_SHARE $DESTINATION_FOLDER"
sudo mkdir -p $DESTINATION_FOLDER
sudo umount -f $DESTINATION_FOLDER 2>/dev/null
sudo vmhgfs-fuse -o allow_other -o auto_unmount ".host:/$FOLDER_TO_SHARE" $DESTINATION_FOLDER