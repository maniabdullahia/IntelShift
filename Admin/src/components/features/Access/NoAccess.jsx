
import Button from '../../ui/Button.jsx';
import { Lock } from 'lucide-react';
import { NavLink } from 'react-router-dom';

export default function NoAccess({ message = 'You do not have permission to view this page.' }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-(--bg) p-6">
      <div className="w-full max-w-2xl bg-white border border-(--border) rounded-2xl shadow-sm p-8">
        <div className="text-center">
          <div className="mx-auto w-20 h-20 rounded-xl flex items-center justify-center mb-4" style={{ background: 'linear-gradient(180deg, rgba(74,144,226,0.08), rgba(74,144,226,0.03))' }}>
            <Lock size={34} className="text-(--blue)" />
          </div>

          <h2 className="font-serif text-2xl text-(--primary) mb-2">Authenticate Yourself</h2>
          <p className="text-sm text-(--text-light) mb-6">{message}</p>

          <div className="max-w-xs mx-auto">
            <NavLink to="/login" className="block">
              <Button title="Log in" variant="primary" className="w-full" />
            </NavLink>
          </div>
        </div>

        {/* <div className="mt-8">
          <h4 className="text-sm text-(--primary) mb-3">What to do next</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="flex items-start gap-3 p-3 rounded-lg border border-(--border) bg-(--card)">
              <div className="p-2 rounded-md" style={{ background: 'rgba(74,144,226,0.06)' }}>
                <UserCheck size={20} className="text-(--blue)" />
              </div>
              <div>
                <div className="text-[14px] font-semibold text-(--primary)">Sign in</div>
                <div className="text-[13px] text-(--text-light)">Use your admin account to authenticate.</div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg border border-(--border) bg-(--card)">
              <div className="p-2 rounded-md" style={{ background: 'rgba(78,205,196,0.06)' }}>
                <Mail size={20} className="text-(--secondary)" />
              </div>
              <div>
                <div className="text-[14px] font-semibold text-(--primary)">Request access</div>
                <div className="text-[13px] text-(--text-light)">If you need admin rights, submit a request.</div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg border border-(--border) bg-(--card)">
              <div className="p-2 rounded-md" style={{ background: 'rgba(255,214,165,0.06)' }}>
                <Clock size={20} className="text-(--warning)" />
              </div>
              <div>
                <div className="text-[14px] font-semibold text-(--primary)">Wait for approval</div>
                <div className="text-[13px] text-(--text-light)">Check your email for updates from admins.</div>
              </div>
            </div>
          </div>
        </div> */}
      </div>
    </div>
  );
}

