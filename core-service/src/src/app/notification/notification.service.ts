import { firebaseMessaging } from '../firebase/firebase';
import { UserDevice } from '../../db/app-db/models/userdevice.model';

const FCM_BATCH_SIZE = 500;

export async function getActiveTokens(where: Record<string, any> = {}): Promise<{ token: string; userId: string | null }[]> {
  const devices = await UserDevice.findAll({
    where: { is_active: true, ...where },
    attributes: ['fcm_token', 'user_id'],
  });
  return devices.map(d => ({ token: d.fcm_token, userId: d.user_id }));
}

export async function sendMulticast(
  tokenEntries: { token: string; userId: string | null }[],
  title: string,
  body: string,
  extras: { imageUrl?: string; data?: Record<string, string> } = {}
): Promise<{ sent: number; failed: number }> {
  let sent = 0;
  let failed = 0;

  for (let i = 0; i < tokenEntries.length; i += FCM_BATCH_SIZE) {
    const batch = tokenEntries.slice(i, i + FCM_BATCH_SIZE);
    const tokens = batch.map(e => e.token);

    let response;
    try {
      response = await firebaseMessaging.sendEachForMulticast({
        tokens,
        notification: {
          title,
          body,
          ...(extras.imageUrl ? { imageUrl: extras.imageUrl } : {}),
        },
        ...(extras.data && Object.keys(extras.data).length > 0 ? { data: extras.data } : {}),
      });
    } catch (err) {
      console.error('[FCM] Batch send error:', err);
      failed += batch.length;
      continue;
    }

    for (let idx = 0; idx < batch.length; idx++) {
      const result = response.responses[idx];
      if (result.success) {
        sent++;
      } else {
        failed++;
        if (result.error?.code === 'messaging/registration-token-not-registered') {
          UserDevice.update({ is_active: false }, { where: { fcm_token: batch[idx].token } }).catch(() => {});
        }
      }
    }
  }

  return { sent, failed };
}
