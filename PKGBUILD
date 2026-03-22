# Maintainer: Egor Kurochkin <itsegork@gmail.com>
pkgname=adb-file-manager
pkgver=prototype_3.0.0_build_22032026_0720
pkgrel=1
pkgdesc="GUI File Manager for Android devices using ADB"
arch=('any')
url="https://github.com/itsegork/adb-file-manager"
license=('MIT')
depends=('python' 'android-tools' 'python-gobject' 'scrcpy' 'noto-fonts-emoji' 'python-requests', 'python-gi', 'libadwaita')
makedepends=('git' 'python-setuptools')
source=("$pkgname::git+https://github.com/itsegork/adb-file-manager.git")
sha256sums=('SKIP')

package() {
    cd "$srcdir/$pkgname"

    install -dm755 "$pkgdir/usr/share/$pkgname"
    install -dm755 "$pkgdir/usr/bin"
    install -dm755 "$pkgdir/usr/share/applications"
    install -dm755 "$pkgdir/usr/share/pixmaps"
    
    cp -r src/* "$pkgdir/usr/share/$pkgname/"
    cat > "$pkgdir/usr/bin/$pkgname" << EOF
#!/bin/bash
cd /usr/share/$pkgname
python3 main.py
EOF
    chmod +x "$pkgdir/usr/bin/$pkgname"
    cat > "$pkgdir/usr/share/applications/$pkgname.desktop" << EOF
[Desktop Entry]
Name=ADB File Manager
Comment=Manage files on Android devices via ADB
Exec=$pkgname
Terminal=false
Type=Application
Categories=Utility
Keywords=android;adb;file;manager;
EOF
}
