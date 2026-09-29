
import { useState } from 'react';
import Button from '../../components/ui/Button.jsx';
import { Mail, Lock, Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import useAuthStore from '../../store/auth.store.js';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);

  const login = useAuthStore((state) => state.login);


  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      setLoading(true);

      await login(email, password);
      navigate('/')

      // console.log('Login result:', loginResult);

      // if (loginResult.success) {
      //   navigate('/');
      // } else {
      //   alert(`Login failed: ${loginResult.error}`);
      // }
    } catch (error) {
      console.error(error);
      alert('Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-(--bg)">
      {/* Left Sidebar - Branding */}
      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto bg-[linear-gradient(135deg,var(--primary)_0%,#0f0f22_100%)] p-12 text-white box-border max-h-screen">
        <div className="max-w-100 text-center">
          <h1 className="mb-4 font-['DM_Serif_Display',serif] text-[48px] font-bold italic text-(--card)!">
            Intelshift AI
          </h1>
          <p className="mb-8 text-[16px] leading-[1.6] text-white/85">
            Competitor Intelligence Admin Console
          </p>
          <p className="text-[14px] leading-[1.8] text-white/65">
            Monitor competitor activity, manage customer workspaces, and track platform performance in one unified dashboard.
          </p>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex flex-1 items-center justify-center overflow-y-auto p-12 box-border max-h-screen">
        <div className="w-full max-w-100">
          {/* Form Header */}
          <div className="mb-10">
            <h2 className="mb-2 font-['DM_Sans',sans-serif] text-[28px] font-bold text-(--primary)">
              Sign In
            </h2>
            <p className="text-[14px] text-(--text-light)">
              Enter your admin credentials to access the console
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleLogin}>
            {/* Email Input */}
            <div className="mb-5">
              <label className="mb-2 block text-[14px] font-bold text-(--primary)">
                Email Address
              </label>
              <div className="relative">
                <Mail size={18} className="pointer-events-none absolute left-3.5 top-3 text-(--text-light)" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@compantelligence.com"
                  required
                  className="box-border w-full rounded-lg border border-(--border) bg-white px-3.5 py-3 pl-10 font-['DM_Sans',sans-serif] text-[14px] text-(--text)"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="mb-6">
              <label className="mb-2 block text-[14px] font-bold text-(--primary)">
                Password
              </label>
              <div className="relative">
                <Lock size={18} className="pointer-events-none absolute left-3.5 top-3 text-(--text-light)" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="box-border w-full rounded-lg border border-(--border) bg-white px-10 py-3 font-['DM_Sans',sans-serif] text-[14px] text-(--text)"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3 flex cursor-pointer items-center border-none bg-transparent text-(--text-light)"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="mb-8 flex items-center justify-between text-[14px]">
              <label className="flex cursor-pointer items-center text-(--text)">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="mr-2 h-4 w-4 cursor-pointer accent-(--accent)"
                />
                Remember me
              </label>
              <a
                href="#"
                className="font-semibold text-(--accent) no-underline transition-opacity hover:opacity-80"
              >
                Forgot Password?
              </a>
            </div>

            {/* Sign In Button */}
            <Button
              title={loading ? 'Signing In...' : 'Sign In'}
              variant="primary"
              fullWidth
              loading={loading}
              type="submit"
              disabled={loading}
            />
          </form>

          {/* Footer Text */}
            <div className="h-3" />

          {/* Footer Text
          <p style={{ textAlign: 'center', color: 'var(--text-light)', fontSize: '13px' }}>
            Don't have access?{' '}
            <a
              href="#"
              style={{
                color: 'var(--accent)',
                textDecoration: 'none',
                fontWeight: '600',
              }}
            >
              Request Access
            </a>
          </p> */}
        </div>
      </div>
    </div>
  );
}

export default Login;
