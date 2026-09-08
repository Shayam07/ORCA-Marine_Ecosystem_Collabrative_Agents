import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.orca.marine',
  appName: 'ORCA',
  webDir: 'dist',
  server: {
    androidScheme: 'http',
    cleartext: true,
  },
  plugins: {
    LocalNotifications: {
      smallIcon: 'ic_stat_icon_config_sample',
      iconColor: '#06b6d4',
      sound: 'beep.wav',
    },
    Geolocation: {
      // High accuracy GPS enabled for marine positioning
    },
  },
};

export default config;
