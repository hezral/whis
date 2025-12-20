### Build using meson 
Ensure you have these dependencies installed

* python3
* python3-gi
* libgranite-7-dev
* wl-clipboard
* wtype
* hyprvoice https://github.com/leonardotrapani/hyprvoice (requires golang to compile)


Download the updated source [here](https://github.com/hezral/whis/archive/master.zip), or use git:
```bash
git clone https://github.com/hezral/whis.git
cd whis
meson build --prefix=/usr
cd build
ninja build
sudo ninja install
```
The desktop launcher should show up on the application launcher for your desktop environment
if it doesn't, try running
```
com.github.hezral.whis
```

