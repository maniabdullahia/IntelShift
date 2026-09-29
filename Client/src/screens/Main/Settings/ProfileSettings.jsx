import { useMemo, useRef, useState } from 'react'
import Input from '../../../components/ui/Input'
import Button from '../../../components/ui/Button'
import Swal from '../../../components/shared/Alert'

import useAuthStore from '../../../store/auth.store'

import { changePassword } from '../../../api/user.api'
import { Camera, Upload, X } from 'lucide-react'

function ProfileSettings() {

  const user = useAuthStore((state) => state.user)
  const updateUserProfile = useAuthStore((state) => state.updateUserProfile)
  const syncUser = useAuthStore((state) => state.syncUser)

  const isSocial = user?.provider && user.provider !== 'local'

  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [profilePicture, setProfilePicture] = useState(user?.profilePicture || '');
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const fileInputRef = useRef(null);

  const initialName = user?.name || '';
  const initialEmail = user?.email || '';
  const initialProfilePicture = user?.profilePicture || '';

  // Email is read-only (changes go through support), so it's not part of the
  // editable diff.
  const hasProfileChanges = useMemo(() => {
    return (
      name.trim() !== initialName.trim() ||
      profilePicture !== initialProfilePicture
    );
  }, [initialName, initialProfilePicture, name, profilePicture]);

  const initials = useMemo(() => {
    if (!name?.trim()) return 'U';
    return name
      .trim()
      .split(' ')
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() || '')
      .join('');
  }, [name]);

  const passwordChecks = useMemo(() => {
    return {
      minLength: newPassword.length >= 8,
      uppercase: /[A-Z]/.test(newPassword),
      lowercase: /[a-z]/.test(newPassword),
      number: /\d/.test(newPassword),
      symbol: /[^A-Za-z0-9]/.test(newPassword),
    };
  }, [newPassword]);

  const passwordScore = useMemo(() => {
    return Object.values(passwordChecks).filter(Boolean).length;
  }, [passwordChecks]);

  const passwordStrength = useMemo(() => {
    if (!newPassword) return { label: 'No password entered', color: 'text-(--text-light)', fill: '0%' };
    if (passwordScore <= 2) return { label: 'Weak', color: 'text-(--danger)', fill: '35%' };
    if (passwordScore <= 4) return { label: 'Medium', color: 'text-(--warning)', fill: '70%' };
    return { label: 'Strong', color: 'text-(--success)', fill: '100%' };
  }, [newPassword, passwordScore]);


  async function handleProfileUpdate() {
    const trimmedName = name.trim();

    if(trimmedName.length < 2) {
      Swal.fire({
        icon: 'error',
        title: 'Invalid Name',
        text: 'Name must be at least 2 characters long.',
      })
      return;
    }

    if (!hasProfileChanges) {
      Swal.fire({
        icon: 'info',
        title: 'No Changes',
        text: 'Update any field before saving.',
      });
      return;
    }

    try {
      setIsSavingProfile(true);
      await Promise.resolve(updateUserProfile({
        name: trimmedName,
        profilePicture,
      }));
      Swal.fire({ icon: 'success', title: 'Profile saved', timer: 2200, showConfirmButton: false });
    } catch (e) {
      Swal.fire({ icon: 'error', title: 'Update failed', text: e?.message || 'Could not save your profile.', confirmButtonColor: '#ff6b6b' });
    } finally {
      setIsSavingProfile(false);
    }
  }

  function handleProfilePictureSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      Swal.fire({
        icon: 'error',
        title: 'Invalid File',
        text: 'Please upload an image file.',
      });
      event.target.value = '';
      return;
    }

    const maxBytes = 2 * 1024 * 1024;
    if (file.size > maxBytes) {
      Swal.fire({
        icon: 'error',
        title: 'File Too Large',
        text: 'Profile image must be smaller than 2MB.',
      });
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = typeof reader.result === 'string' ? reader.result : '';
      setProfilePicture(base64);
    };
    reader.readAsDataURL(file);
  }

  function handleProfilePictureRemove() {
    setProfilePicture('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  async function handleChangePassword() {
    if(!currentPassword || !newPassword) {
      Swal.fire({
        icon: 'error',
        title: 'Missing Fields',
        text: 'Please fill in both current and new password fields.',
      })
      return;
    }
    if(passwordScore < 4) {
      Swal.fire({
        icon: 'error',
        title: 'Weak Password',
        text: 'Use a stronger password with at least 8 characters and a mix of character types.',
      })
      return;
    }

    try {
      setIsChangingPassword(true);
      await changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      Swal.fire({ icon: 'success', title: 'Password changed', timer: 2200, showConfirmButton: false });
    } catch (e) {
      Swal.fire({ icon: 'error', title: 'Could not change password', text: e?.message || 'Please try again.', confirmButtonColor: '#ff6b6b' });
    } finally {
      setIsChangingPassword(false);
    }

  }

  return (
    <section className="relative mx-auto w-full max-w-6xl overflow-hidden px-4 py-6 sm:px-6 sm:py-8">
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-[rgba(78,205,196,0.16)] blur-3xl" />
      <div className="pointer-events-none absolute -bottom-28 -left-20 h-64 w-64 rounded-full bg-[rgba(255,107,107,0.14)] blur-3xl" />

      <div className="relative rounded-3xl border border-(--border) bg-linear-to-r from-(--primary) to-[rgba(26,26,46,0.9)] p-5 shadow-md sm:p-8">
        <div className="inline-flex items-center rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white/90">
          Account Center
        </div>
        <h2 className="mt-3 font-[Inter] tracking-tight text-3xl font-semibold text-white sm:text-4xl">
          Profile Settings
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-white/80 sm:text-base">
          Manage your personal details and security in one place.
        </p>
      </div>

      <div className="relative mt-6 space-y-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-8 lg:col-span-8">
            <div className="mb-6 flex items-center justify-between gap-3">
              <h4 className="text-lg font-semibold sm:text-xl">Personal Information</h4>
              <div className="flex items-center gap-2">
                {hasProfileChanges && (
                  <span className="rounded-full bg-[rgba(78,205,196,0.16)] px-2.5 py-1 text-xs font-semibold text-(--primary)">
                    Unsaved Changes
                  </span>
                )}
                <span className="h-2 w-14 rounded-full bg-(--secondary)" />
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <label htmlFor='name' className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base">
                  Full Name
                </label>
                <Input
                  type="text"
                  id="name"
                  placeholder="Enter your name"
                  className="h-11 w-full rounded-xl border border-slate-200 px-4 text-sm focus:border-[#ff6b6b] focus:ring-2 focus:ring-[#ff6b6b]/20 sm:h-12 sm:text-base"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="email" className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base">
                  Email Address
                </label>
                <Input
                  type="email"
                  id="email"
                  disabled
                  readOnly
                  className="h-11 w-full cursor-not-allowed rounded-xl border border-slate-200 bg-[rgba(0,0,0,0.03)] px-4 text-sm text-(--text-light) sm:h-12 sm:text-base"
                  value={email}
                />
                <p className="mt-1.5 text-xs text-(--text-light)">
                  Your email is your account identity and can't be changed here. Contact support to update it.
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <Button
                title={isSavingProfile ? 'Saving...' : 'Save Changes'}
                onClick={handleProfileUpdate}
                className="w-full sm:w-auto"
                disabled={isSavingProfile || !hasProfileChanges}
              />
            </div>
          </div>

          <div className="rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-8 lg:col-span-4">
            <h4 className="mb-4 flex items-center gap-3 text-lg font-semibold sm:text-xl">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[rgba(78,205,196,0.16)]">
                <Camera className='text-(--primary)' />
              </span>
              Profile Picture
            </h4>

            <div className="mb-5 flex flex-col items-center gap-4">
              <div className="relative">
                {profilePicture ? (
                  <img
                    src={profilePicture}
                    alt="Profile"
                    className="h-32 w-32 rounded-full border border-(--border) object-cover shadow-sm sm:h-36 sm:w-36"
                  />
                ) : (
                  <div className="flex h-32 w-32 items-center justify-center rounded-full bg-linear-to-r from-(--secondary) to-(--accent) text-3xl font-semibold text-white shadow-sm sm:h-36 sm:w-36 sm:text-4xl">
                    {initials}
                  </div>
                )}
              </div>

              <div className="w-full space-y-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-(--border) bg-white px-3 py-2 text-sm font-semibold text-(--primary) transition hover:bg-[rgba(78,205,196,0.1)]"
                >
                  <Upload size={16} />
                  Upload Image
                </button>

                <button
                  type="button"
                  onClick={handleProfilePictureRemove}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-(--border) bg-white px-3 py-2 text-sm font-semibold text-(--text-light) transition hover:bg-[rgba(255,107,107,0.08)]"
                  disabled={!profilePicture}
                >
                  <X size={16} />
                  Remove
                </button>
              </div>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleProfilePictureSelect}
            />

            <p className="text-xs text-(--text-light)">
              Recommended: square image, JPG/PNG/WebP, max 2MB.
            </p>
          </div>
        </div>

        <div className="rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-8">
          <div className="mb-6 flex items-center justify-between gap-3">
            <h4 className="text-lg font-semibold sm:text-xl">Change Password</h4>
            <div className="flex items-center gap-2">
              {!!newPassword && (
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${passwordStrength.color} bg-[rgba(0,0,0,0.04)]`}>
                  {passwordStrength.label}
                </span>
              )}
              <span className="h-2 w-14 rounded-full bg-(--accent)" />
            </div>
          </div>

          {isSocial && (
            <div className="mb-6 rounded-xl border border-(--border) bg-[rgba(0,0,0,0.02)] px-4 py-3 text-sm text-(--text-light)">
              You signed in with {user.provider === 'google' ? 'Google' : 'Facebook'}, so there's no password to change here. Manage sign-in from your {user.provider === 'google' ? 'Google' : 'Facebook'} account.
            </div>
          )}
          <div className={`space-y-6 ${isSocial ? 'pointer-events-none opacity-50' : ''}`}>
            <div>
              <label htmlFor='currentPassword' className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base">
                Current Password <span className='text-(--accent)'>*</span>
              </label>
              <Input
                type="password"
                id="currentPassword"
                placeholder="Enter your current password"
                className="h-11 w-full rounded-xl border border-slate-200 px-4 text-sm focus:border-[#ff6b6b] focus:ring-2 focus:ring-[#ff6b6b]/20 sm:h-12 sm:text-base"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="newPassword" className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base">
                New Password <span className='text-(--accent)'>*</span>
              </label>
              <Input
                type="password"
                id="newPassword"
                placeholder="Enter your new password"
                className="h-11 w-full rounded-xl border border-slate-200 px-4 text-sm focus:border-[#ff6b6b] focus:ring-2 focus:ring-[#ff6b6b]/20 sm:h-12 sm:text-base"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />

              {newPassword && (
                <div className="mt-3 space-y-3 rounded-2xl bg-[rgba(0,0,0,0.02)] p-3">
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="text-(--text-light)">Password Strength</span>
                      <span className={`font-semibold ${passwordStrength.color}`}>{passwordStrength.label}</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-(--border)">
                      <div
                        className="h-2 rounded-full bg-(--secondary) transition-all duration-300"
                        style={{ width: passwordStrength.fill }}
                      />
                    </div>
                  </div>

                  <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
                    <li className={passwordChecks.minLength ? 'text-(--success)' : 'text-(--text-light)'}>At least 8 characters</li>
                    <li className={passwordChecks.uppercase ? 'text-(--success)' : 'text-(--text-light)'}>1 uppercase letter</li>
                    <li className={passwordChecks.lowercase ? 'text-(--success)' : 'text-(--text-light)'}>1 lowercase letter</li>
                    <li className={passwordChecks.number ? 'text-(--success)' : 'text-(--text-light)'}>1 number</li>
                    <li className={passwordChecks.symbol ? 'text-(--success)' : 'text-(--text-light)'}>1 special character</li>
                  </ul>
                </div>
              )}
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <Button
              title={isChangingPassword ? 'Updating...' : 'Change password'}
              onClick={handleChangePassword}
              className="w-full sm:w-auto"
              disabled={isSocial || isChangingPassword || !currentPassword || !newPassword}
            />
          </div>
        </div>
      </div>

      {/* Account closure / deletion now lives in Billing & Usage (single hub for
          account-lifecycle actions). */}

    </section>
  )
}

export default ProfileSettings
