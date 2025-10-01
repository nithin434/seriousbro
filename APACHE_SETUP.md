# SYNTEXA Apache2 Setup with SSL

## 🚀 Complete Setup for syntexa.app

This guide will set up Apache2 to run your Flask application directly with SSL certificates.

## 📋 Prerequisites

- ✅ DNS configured for syntexa.app pointing to your server
- ✅ Virtual environment at `/home/clouduser/GEt/venv`
- ✅ Root access (sudo)

## 🔧 Installation Steps

### Step 1: Install Apache2 and Configure Flask App

```bash
# Run as root
sudo ./install_apache.sh
```

This will:
- Install Apache2 and required modules
- Configure WSGI for your Flask app
- Set up virtual hosts for HTTP and HTTPS
- Configure static file serving
- Set proper permissions

### Step 2: Install SSL Certificates

```bash
# Run as root
sudo ./install_ssl.sh
```

This will:
- Install Let's Encrypt certbot
- Obtain SSL certificates for syntexa.app
- Configure auto-renewal
- Test SSL configuration

## 🌐 Access Your Application

After installation:
- **HTTPS**: https://syntexa.app
- **HTTP**: http://syntexa.app (redirects to HTTPS)

## 📁 Files Created

- `syntexa_apache.conf` - Apache2 configuration
- `wsgi.py` - WSGI entry point for Flask
- `install_apache.sh` - Apache2 installation script
- `install_ssl.sh` - SSL certificate installation script

## 🔍 Configuration Details

### Apache2 Configuration
- **HTTP**: Redirects all traffic to HTTPS
- **HTTPS**: Serves Flask app with SSL
- **Static Files**: Served directly by Apache
- **Uploads**: Properly configured for file uploads
- **Security Headers**: HSTS, XSS protection, etc.

### WSGI Configuration
- Uses your virtual environment
- Runs Flask app directly
- Proper Python path configuration
- Production environment settings

## 🛠️ Troubleshooting

### Check Apache Status
```bash
sudo systemctl status apache2
```

### Check Apache Configuration
```bash
sudo apache2ctl configtest
```

### View Logs
```bash
# Error logs
sudo tail -f /var/log/apache2/syntexa_https_error.log

# Access logs
sudo tail -f /var/log/apache2/syntexa_https_access.log
```

### Test Flask App
```bash
# Test WSGI directly
python3 wsgi.py
```

### Check SSL Certificate
```bash
# Check certificate status
sudo certbot certificates

# Test SSL
curl -I https://syntexa.app
```

## 🔄 Maintenance

### Renew SSL Certificates
```bash
sudo certbot renew
```

### Restart Apache
```bash
sudo systemctl restart apache2
```

### Update Application
```bash
# After updating your Flask app
sudo systemctl reload apache2
```

## 📊 Performance Features

- ✅ **Static File Caching**: 1-year cache for static assets
- ✅ **Gzip Compression**: Enabled for better performance
- ✅ **Security Headers**: Comprehensive security configuration
- ✅ **SSL Optimization**: Modern SSL configuration
- ✅ **Direct WSGI**: No proxy overhead

## 🎯 Benefits of This Setup

1. **Direct Integration**: Flask runs directly under Apache2
2. **SSL Security**: Full HTTPS with Let's Encrypt
3. **Performance**: Optimized static file serving
4. **Security**: Comprehensive security headers
5. **Maintenance**: Auto-renewing SSL certificates
6. **Scalability**: Production-ready configuration

Your SYNTEXA application is now ready to serve at https://syntexa.app with full SSL security!

