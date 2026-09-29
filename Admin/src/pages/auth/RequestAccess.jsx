import { useState } from 'react';
import Button from '../../components/ui/Button.jsx';
import { Mail, User, CheckCircle, MessageSquare } from 'lucide-react';

function RequestAccess() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setLoading(true);
    // Simulate API request
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
    }, 1200);
  };

  if (submitted) {
    return (
      <div className="flex h-screen items-center justify-center bg-(--bg)">
        <div className="w-full max-w-180 rounded-xl border border-(--border) bg-white p-8 text-center">
          <CheckCircle size={48} color="var(--secondary)" className="mb-3" />
          <h2 className="mb-2 text-[24px] font-bold text-(--primary)">Request Submitted</h2>
          <p className="mb-4.5 text-(--text-light)">Thanks — your request has been sent to the admin team. We'll review and respond via email.</p>
          <div className="flex justify-center">
            <Button title="Back to Sign In" variant="ghost" onClick={() => window.location.href = '/auth/login'} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen items-center justify-center bg-(--bg)">
      <div className="box-border grid w-full max-w-180 grid-cols-[1fr_420px] gap-7 p-6">
        {/* Left - Info */}
        <div className="h-full rounded-xl border border-(--border) bg-[linear-gradient(180deg,white,var(--bg))] p-7">
          <h1 className="mb-2 font-['DM_Serif_Display',serif] text-[28px] font-bold text-(--primary)">Request Admin Access</h1>
          <p className="mb-4 text-[14px] text-(--text-light)">Provide the details below so the platform administrators can review and grant access to the admin console.</p>
          <div className="mt-3 text-[13px] text-(--text-light)">
            <div className="mb-3 flex items-start gap-2">
              <CheckCircle size={18} color="var(--secondary)" />
              <div>
                Admins will verify your identity and workspace ownership.
              </div>
            </div>
            <div className="mb-3 flex items-start gap-2">
              <MessageSquare size={18} color="var(--blue)" />
              <div>
                You will receive status updates via email.
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle size={18} color="var(--success)" />
              <div>
                Access is granted based on role and approval.
              </div>
            </div>
          </div>
        </div>

        {/* Right - Form */}
        <div className="rounded-xl border border-(--border) bg-white p-7">
          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label className="mb-2 block text-[13px] font-bold text-(--primary)">Full name</label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-3 text-(--text-light)" />
                <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your full name" className="box-border w-full rounded-lg border border-(--border) px-3.5 py-3 pl-9 text-[14px]" />
              </div>
            </div>

            <div className="mb-3">
              <label className="mb-2 block text-[13px] font-bold text-(--primary)">Work email</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-3 text-(--text-light)" />
                <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" className="box-border w-full rounded-lg border border-(--border) px-3.5 py-3 pl-9 text-[14px]" />
              </div>
            </div>

            <div className="mb-3">
              <label className="mb-2 block text-[13px] font-bold text-(--primary)">Workspace</label>
              <input required value={workspace} onChange={(e) => setWorkspace(e.target.value)} placeholder="Workspace / Company name" className="box-border w-full rounded-lg border border-(--border) px-3.5 py-3 text-[14px]" />
            </div>

            <div className="mb-4">
              <label className="mb-2 block text-[13px] font-bold text-(--primary)">Reason for access</label>
              <textarea required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Describe why you need admin access" rows={4} className="box-border w-full resize-y rounded-lg border border-(--border) px-3.5 py-3 text-[14px]" />
            </div>

            <div className="flex items-center gap-3">
              <Button title={loading ? 'Sending...' : 'Request Access'} variant="primary" type="submit" loading={loading} />
              <Button title="Cancel" variant="ghost" onClick={() => window.location.href = '/auth/login'} />
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default RequestAccess;
