import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

function Input({ id, placeholder = "Enter text", value, onChange, type = "text", disabled = false, ...rest }) {
  const [isFocused, setIsFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";


  const inputStyles = {
    width: '100%',
    padding: '12px 14px',
    paddingRight: isPassword ? '42px' : '14px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '14px',
    fontFamily: 'var(--font-body)',
    color: 'var(--text)',
    backgroundColor: 'var(--card)',
    border: isFocused ? '1px solid var(--accent)' : '1px solid var(--border)',
    boxShadow: isFocused
      ? '0 0 0 3px rgba(255, 107, 107, 0.16)'
      : '0 1px 2px rgba(0, 0, 0, 0.04)',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
    outline: 'none',
    minHeight: '44px',
    opacity: disabled ? '0.7' : '1',
    cursor: disabled ? 'not-allowed' : 'text',
  };

  return (
    <div className='relative w-full'>
      <input
        id={id}
        type={isPassword ? (showPassword ? "text" : "password") : type}
        style={inputStyles}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        disabled={disabled}
        aria-disabled={disabled}
        {...rest}
      />
      <span>
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-(--text-light) transition hover:bg-[rgba(0,0,0,0.05)] hover:text-(--text)"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            tabIndex={disabled ? -1 : 0}
            disabled={disabled}
          >
            {showPassword ? <Eye size={16} /> : <EyeOff size={16} />}
          </button>
        ) }
      </span>
        
    </div>
    
  );
}

export default Input
