# Third-party components

Runtime dependencies and their transitive components are recorded in `package-lock.json` and the Android Gradle files. This directory uses React (MIT), Capacitor (MIT), Lucide (ISC), JSch maintained fork (BSD-style), Bouncy Castle (MIT), and AndroidX (Apache 2.0). Refer to each upstream package's bundled license for full terms.

Bundled fonts: Orbitron, Rajdhani and ZCOOL QingKe HuangYou, distributed under the SIL Open Font License. Full license texts are included in `public/fonts/*-OFL.txt`. Other OFL texts in that directory accompany the desktop font collection; only the three font binaries used by this mobile app are bundled.

The remote Python probe is shared with the parent GPU Checker project. Test SSH credentials and synthetic data in development scripts are fixtures, never user credentials, and are not packaged into the Android runtime.
