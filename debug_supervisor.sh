#!/bin/bash
# Comprehensive supervisor/systemd diagnostics for irrigator update restart issues

echo "=========================================="
echo "Irrigator Update Restart Diagnostics"
echo "=========================================="
echo ""

echo "[1] Checking if supervisord is running..."
systemctl is-active supervisor > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ supervisord is running via systemd"
    systemctl status supervisor --no-pager | head -20
else
    ps aux | grep -i supervisor | grep -v grep
    if [ $? -eq 0 ]; then
        echo "✓ supervisord process found (not via systemd)"
    else
        echo "✗ supervisord does not appear to be running"
    fi
fi
echo ""

echo "[2] Checking supervisorctl accessibility..."
supervisorctl status > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ supervisorctl is accessible"
    supervisorctl status
else
    echo "✗ supervisorctl failed - trying with sudo..."
    sudo supervisorctl status 2>&1 | head -20
fi
echo ""

echo "[3] Checking webapp program status..."
supervisorctl status webapp 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ Could not query webapp status via supervisorctl"
fi
echo ""

echo "[4] Checking supervisor configuration..."
if [ -f /etc/supervisor/conf.d/webapp.conf ]; then
    echo "✓ Found /etc/supervisor/conf.d/webapp.conf"
    cat /etc/supervisor/conf.d/webapp.conf
elif [ -f /etc/supervisor/supervisord.conf ]; then
    echo "Checking supervisord.conf for include directive..."
    grep -i "include" /etc/supervisor/supervisord.conf | head -5
fi
echo ""

echo "[5] Checking gunicorn process..."
ps aux | grep -i gunicorn | grep -v grep
if [ $? -ne 0 ]; then
    echo "✗ gunicorn not running (this is normal after update)"
else
    echo "✓ gunicorn is running"
fi
echo ""

echo "[6] Checking Python syntax of app.py..."
cd /usr/local/bin/irrigator 2>/dev/null || cd . 
python3 -m py_compile app.py 2>&1
if [ $? -eq 0 ]; then
    echo "✓ app.py syntax is valid"
else
    echo "✗ app.py has syntax errors (preventing restart!)"
fi
echo ""

echo "[7] Testing manual restart..."
echo "Attempting: supervisorctl restart webapp"
supervisorctl restart webapp 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Restart via supervisorctl succeeded"
    sleep 2
    supervisorctl status webapp
else
    echo "✗ Restart via supervisorctl failed, trying systemctl..."
    systemctl restart supervisor 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ Restarted supervisor via systemctl"
        sleep 2
        supervisorctl status webapp 2>/dev/null || echo "(waiting for supervisor to stabilize)"
    else
        echo "✗ All restart methods failed"
    fi
fi
echo ""

echo "[8] Checking supervisor logs..."
if [ -f /var/log/supervisor/supervisord.log ]; then
    echo "Last 30 lines of supervisord.log:"
    tail -30 /var/log/supervisor/supervisord.log
fi
echo ""

echo "[9] Checking webapp logs..."
if [ -d /usr/local/bin/irrigator/logs ]; then
    echo "Recent webapp error log:"
    tail -20 /usr/local/bin/irrigator/logs/webapp.err.log 2>/dev/null || echo "(no err.log)"
    echo "Recent webapp output log:"
    tail -20 /usr/local/bin/irrigator/logs/webapp.out.log 2>/dev/null || echo "(no out.log)"
fi
echo ""

echo "=========================================="
echo "Diagnostics complete. Please share output with developer."
echo "=========================================="
