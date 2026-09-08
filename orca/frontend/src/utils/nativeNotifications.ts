import { Capacitor } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';

export interface AlertNotificationOptions {
  title: string;
  body: string;
  id?: number;
}

/**
 * Cross-platform Notification service for marine weather alerts,
 * geofence boundaries, and PFZ updates.
 */
export async function sendMarineAlert(options: AlertNotificationOptions): Promise<void> {
  const isNative = Capacitor.isNativePlatform();

  if (isNative) {
    try {
      const perm = await LocalNotifications.checkPermissions();
      if (perm.display !== 'granted') {
        const req = await LocalNotifications.requestPermissions();
        if (req.display !== 'granted') return;
      }

      await LocalNotifications.schedule({
        notifications: [
          {
            id: options.id || Math.floor(Math.random() * 100000),
            title: options.title,
            body: options.body,
            schedule: { at: new Date(Date.now() + 500) },
            sound: undefined,
          },
        ],
      });
      return;
    } catch (e) {
      console.warn('Capacitor local notification failed:', e);
    }
  }

  // Web fallback
  if (typeof window !== 'undefined' && 'Notification' in window) {
    try {
      if (Notification.permission === 'granted') {
        new Notification(options.title, {
          body: options.body,
          icon: '/vite.svg',
        });
      } else if (Notification.permission !== 'denied') {
        const req = await Notification.requestPermission();
        if (req === 'granted') {
          new Notification(options.title, {
            body: options.body,
            icon: '/vite.svg',
          });
        }
      }
    } catch (e) {
      console.warn('Web notification failed:', e);
    }
  }
}
