MagTag Home Automation
======================

Setup
-----

Assuming you have a Homematic IP CCU3 or similar running with CCU-Jack installed.

Copy `config.py.example` to `config.py` and `secrets.py.example` to `secrets.py` and adapt them to your needs.
Choose a fitting font file. RobotoBold 14pt works well. You can create the needed bdf file with the otf2bdf tool:

```bash
otf2bdf Roboto-Bold.ttf -p 14 -o RobotoBold14.bdf
```

