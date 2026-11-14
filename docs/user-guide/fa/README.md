<div dir="rtl">

# راهنمای کاربر ایزی‌دیپلوی (فاز ۰)

## نصب

> نصب‌کننده سیستم را تغییر می‌دهد (Docker، Nginx، فایروال). آن را فقط روی یک سرور یا ماشین مجازی تازه و یک‌بارمصرف اجرا کنید.

پیش‌نیازها: Ubuntu Server نسخهٔ 22.04، 24.04 یا 26.04 (amd64 یا arm64)، دسترسی root، دست‌کم ۱ گیگابایت RAM و ۱۰ گیگابایت فضای خالی.

**نصب با یک دستور** (آخرین نسخه را از GitHub Releases دانلود می‌کند، checksum آن را بررسی و نصب می‌کند):

```bash
curl -fsSL https://raw.githubusercontent.com/algorithmic-mind/EasyDeploy/main/installer/install.sh -o install.sh && sudo bash install.sh
```

گزینه‌های مفید: `--port <پورت>`، `--username <نام>`، `--lang fa` (زبان پیش‌فرض فارسی)، `--no-firewall`، `--version <نسخه>`.

**اگر GitHub روی سرور در دسترس نیست:** فایل `easydeploy-<نسخه>-linux-amd64.tar.gz` و `SHA256SUMS` را از صفحهٔ Releases روی رایانهٔ خود دانلود کنید، هر دو را (به‌همراه `install.sh`) به سرور منتقل کنید و اجرا کنید:

```bash
sudo bash install.sh --release-file easydeploy-<نسخه>-linux-amd64.tar.gz
```

نصب از کد منبع (نسخهٔ توسعه):

```bash
cd frontend && npm ci && npm run build && cd ..
sudo bash installer/install.sh --from-source --yes
```

برای شبکه‌های محدود، مقادیر فایل `installer/mirrors/ir.env` را با آینه‌های مورد اعتماد خود پر کنید و سپس با `--mirror-profile ir` نصب کنید.

> نسخه‌های فعلی پیش‌انتشار هستند: سلامت فایل فقط با SHA-256 بررسی می‌شود و امضای دیجیتال (minisign) در فاز ۶ اضافه می‌شود.

در پایان نصب، آدرس پنل به شکل `https://<IP>:<پورت>/<مسیر-ورود>`، نام کاربری و رمز عبور **فقط یک بار** نمایش داده می‌شود. مرورگر دربارهٔ گواهی خودامضا هشدار می‌دهد که طبیعی است.

## اولین ورود

1. آدرس کامل (همراه با مسیر ورود امن) را باز کنید؛ بدون آن، پنل صفحهٔ «یافت نشد» نشان می‌دهد.
2. با نام کاربری و رمز وارد شوید.
3. از منوی کاربر ← «حساب کاربری»، احراز هویت دومرحله‌ای (TOTP) را فعال و کدهای بازیابی را ذخیره کنید.
4. زبان را از نوار بالا روی «فارسی» بگذارید تا کل رابط راست‌چین شود. تقویم جلالی هم در «حساب کاربری» قابل انتخاب است.

## بازیابی دسترسی (روی سرور، با root)

| دستور | کار |
|---|---|
| `edctl user-info` | نمایش آدرس پنل و نام کاربری |
| `edctl reset-password` | ساخت رمز جدید، باز کردن قفل و خروج همهٔ نشست‌ها |
| `edctl reset-2fa` | غیرفعال کردن احراز هویت دومرحله‌ای |
| `edctl reset-entrance` | ساخت مسیر ورود جدید |
| `edctl reset-allowlist` / `edctl reset-bind-domain` | حذف محدودیت IP / دامنه |
| `edctl set-port 28443` | تغییر پورت پنل |
| `edctl doctor` | بررسی سلامت سرویس‌ها |
| `edctl status` | وضعیت سرویس‌ها |

برای خروجی فارسی: `edctl --lang fa status`

## حذف

```bash
sudo bash /opt/easydeploy/current/installer/uninstall.sh
```

به‌طور پیش‌فرض داده‌های کاربر نگه داشته می‌شوند؛ `--purge --yes` همه‌چیز را حذف می‌کند.

</div>
