import React, { useState } from 'react'
import Button from '../../../components/ui/Button'
import Checkbox from '../../../components/ui/Checkbox'
import Swal from '../../../components/shared/Alert';
import useAuthStore from '../../../store/auth.store';
import { updateAlertSettings, sendTestAlert } from '../../../api/user.api';

function AlertSettings() {
  const user = useAuthStore((state) => state.user);
  const syncUser = useAuthStore((state) => state.syncUser);
  const saved = user?.settings?.alerts || {};

  const [types, setTypes] = useState({
    pricing: saved.pricing ?? true,
    highImpact: saved.highImpact ?? true,
    homepage: saved.homepage ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const toggle = (key) => setTypes((t) => ({ ...t, [key]: !t[key] }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAlertSettings({ alerts: { ...types } });
      await syncUser();
      Swal.fire({ icon: 'success', title: 'Saved', text: 'Your alert settings have been updated.' });
    } catch (e) {
      Swal.fire({ icon: 'error', title: 'Error', text: e.message || 'Could not save settings.', confirmButtonColor: '#ff6b6b' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await sendTestAlert();
      Swal.fire({ icon: 'success', title: 'Test alert sent', text: `A sample alert was sent to ${res?.email || 'your email'} and your notifications.` });
    } catch (e) {
      Swal.fire({ icon: 'error', title: 'Could not send', text: e.message || 'Test alert failed. Check the mail configuration.', confirmButtonColor: '#ff6b6b' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <h2 className="font-['Fraunces',serif] text-3xl text-(--primary) font-semibold sm:text-4xl">
          Alert Settings
        </h2>
        <p className="text-base leading-relaxed text-(--text-light)">
          Configure when and how you receive notifications
        </p>
      </div>

      <div className="mb-6 mt-8 w-full rounded-xl border-l-4 border-(--secondary) bg-[#4ecdc41a] p-4">
        <h2 className="font-semibold text-(--text)">💡 Smart Alerts</h2>
        <p className="text-sm text-(--text-light)">We only alert you for high-impact changes. Low-noise detection ensures you focus on what matters.</p>
      </div>

      <div className="mb-6 w-full rounded-xl bg-white p-5 font-semibold sm:p-8">
        <h2 className="mb-6 text-lg">Alert Types</h2>

        <div className='mb-4 flex gap-4 sm:gap-5'>
          <div className='mt-2'>
            <Checkbox checked={types.pricing} onChange={() => toggle('pricing')} />
          </div>
          <div className='mb-2'>
            <h3 className='font-semibold text-(--text)'>Pricing Changes</h3>
            <p className='text-sm text-(--text-light)'>Get notified when competitors change their pricing</p>
          </div>
        </div>

        <div className='mb-4 flex gap-4 sm:gap-5'>
          <div className='mt-2'>
            <Checkbox checked={types.highImpact} onChange={() => toggle('highImpact')} />
          </div>
          <div className='mb-2'>
            <h3 className='font-semibold text-(--text)'>High-Impact Changes</h3>
            <p className='text-sm text-(--text-light)'>Changes rated high or critical by AI analysis</p>
          </div>
        </div>

        <div className='flex gap-4 sm:gap-5'>
          <div className='mt-2'>
            <Checkbox checked={types.homepage} onChange={() => toggle('homepage')} />
          </div>
          <div className='mb-2'>
            <h3 className='font-semibold text-(--text)'>Homepage Changes</h3>
            <p className='text-sm text-(--text-light)'>Messaging and positioning updates</p>
          </div>
        </div>
      </div>

      <div className="mb-6 w-full rounded-xl border border-(--border) bg-white p-4 text-sm text-(--text-light) sm:p-5">
        You'll be emailed (and notified in-app) whenever a monitoring scan detects a matching change — as often as your plan monitors.
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3 sm:mt-8">
        <Button title={saving ? 'Saving…' : 'Save Settings'} onClick={handleSave} disabled={saving} />
        <Button variant="secondary" title={testing ? 'Sending…' : 'Send test email'} onClick={handleTest} disabled={testing} />
      </div>
    </section>
  )
}

export default AlertSettings
