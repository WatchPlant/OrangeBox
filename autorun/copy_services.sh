sudo cp OrangeBoxButton.service /lib/systemd/system/
sudo cp OrangeBoxLed.service /lib/systemd/system/
sudo cp OrangeBoxStartup.service /lib/systemd/system/
sudo cp OrangeBoxRsync.service /lib/systemd/system/
sudo cp OrangeBoxRsync.timer /lib/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable OrangeBoxButton.service
sudo systemctl enable OrangeBoxRsync.timer
