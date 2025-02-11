#!/bin/sh
 
echo "[i] Mounting \\containers   /home/parrot/containers"
sudo mkdir -p "/home/parrot/containers"
sudo umount -f /home/parrot/containers 2>/dev/null
sudo vmhgfs-fuse -o allow_other -o auto_unmount ".host:/containers" "/home/parrot/containers"
