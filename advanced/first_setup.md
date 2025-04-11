## Before clone (manual)
### Update and upgrade
```bash
sudo apt update
sudo apt install wget nano tzdata
wget -O - apt.radxa.com/focal-stable/public.key | sudo apt-key add -
sudo apt upgrade
```
### Don't request password for sudo
`sudo visudo`  
Add line: `rock ALL=(ALL) NOPASSWD:ALL`

### Set up overlays
`sudo nano /boot/uEnv.txt`
> verbosity=7  
> **overlay_prefix=rockchip**  
> **ootfstype=ext4**  
> fdtfile=rockchip/rk3308-rock-pi-s.dtb  
> console=ttyS0,1500000n8  
> overlays=rk3308-uart0 **rk3308-uart1 rk3308-i2c1 rk3308-pwm2**  
> rootuuid=d99ac41e-e8cc-4c73-a420-e71f15e42042  
> initrdsize=0x8d09d1  
> kernelversion=4.4.143-69-rockchip-g8ccef796d27d  
> initrdimg=initrd.img-4.4.143-69-rockchip-g8ccef796d27d  
> kernelimg=vmlinuz-4.4.143-69-rockchip-g8ccef796d27d 

### Set up fixed MAC address
`sudo nano /boot/uEnv.txt`
> verbosity=7  
> overlay_prefix=rockchip  
> ootfstype=ext4  
> fdtfile=rockchip/rk3308-rock-pi-s.dtb  
> console=ttyS0,1500000n8  
> overlays=rk3308-uart0 rk3308-uart1 rk3308-i2c1 rk3308-pwm2  
> rootuuid=d99ac41e-e8cc-4c73-a420-e71f15e42042  
> initrdsize=0x8d09d1  
> kernelversion=4.4.143-69-rockchip-g8ccef796d27d  
> initrdimg=initrd.img-4.4.143-69-rockchip-g8ccef796d27d  
> kernelimg=vmlinuz-4.4.143-69-rockchip-g8ccef796d27d
> **extraargs=rtl8723ds.rtw_initmac="00:E0:4C:1A:41:C0"**

### Make a swap file
- https://www.digitalocean.com/community/tutorials/how-to-add-swap-space-on-ubuntu-20-04

### Install basic tools
```bash
sudo apt install -y \
    avahi-daemon avahi-discover avahi-utils libnss-mdns mdns-scan avahi-dnsconfd \
    htop \
    ranger \
    git \
    tmux \
    tmuxinator \
    python3-pip \
    dos2unix \
    rsync \
    libglib2.0-dev
```

### Instal GPIO interface
`sudo apt install libmraa build-essential`

### Set up hostname
`sudo nano /etc/hostname`  
`sudo nano /etc/hosts`

### Add user to dialout
`sudo usermod -a -G dialout rock`

### Install python packages
```bash
python3 -m pip install --upgrade pip
python3 -m pip install \
    gitman \
    digi-xbee \
    pyserial \
    pyyaml \
    pyzmq \
    numpy \
    dash \
    pandas \
    dash-bootstrap-components \
    pytelegrambotapi \
    bluepy

sudo pip3 install \
    adafruit-circuitpython-ina219 \
    adafruit-circuitpython-shtc3
```

### Set up SSH
1. Copy authorized_keys from another Orange Box.
1. Copy WP-machine keys from another Orange Box.
1. Copy Rsync keys from another Orange Box.  
```scp -r .ssh rock@<other_box>.local:~```

### Clone
1. `git clone git@github.com:WatchPlant/OrangeBox.git`  
1. `git clone git@github.com:WatchPlant/OB_patches.git`

### Copy config
1. `cd OrangeBox/advanced && bash copy_config.sh`
1. Add this to `~/.bashrc`:
```bash
if [ -f ~/extra_config.sh ]; then
    . ~/extra_config.sh
fi

export MEAS_DIR=/home/rock/measurements
export MEAS_INT=10000
```

### Copy and enable services
1. `cd OrangeBox/autorun && bash copy_services.sh`

### Copy udev rules
1. ...from another Orange Box.
