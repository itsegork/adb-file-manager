# Maintainer: Egor Kurochkin <itsegork@gmail.com>
pkgname=adb-file-manager
pkgver=1.0.0
pkgrel=1
pkgdesc="GUI File Manager for Android devices using ADB"
arch=('any')
url="https://github.com/yourusername/adb-file-manager"
license=('MIT')
depends=('python' 'android-tools' 'tk' 'scrcpy')
makedepends=('python-setuptools')
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
