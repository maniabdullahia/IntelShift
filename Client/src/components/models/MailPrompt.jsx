import { useState } from 'react';
import { Mail } from 'lucide-react';

import Input from '../ui/Input';
import Button from '../ui/Button';

import useModelStore from '../../store/model.store';

function MailPrompt() {
    const [email, setEmail] = useState('');

    const submitModel = useModelStore((state) => state.submitModel);

    const isValidEmail =
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

    function handleSubmit() {
        if (!isValidEmail) return;

        submitModel(email);
    }

    return (
        <div className="w-full max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mb-3">
                        <Mail size={24} className="text-(--accent)" />
                    </div>

                    <h2 className="text-2xl font-bold text-gray-900">
                        Enter Your Email
                    </h2>

                    <p className="text-sm text-gray-500 mt-2">
                        We'll use this email to continue the setup process.
                    </p>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Email Address
                        </label>

                        <Input
                            type="email"
                            placeholder="john@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    handleSubmit();
                                }
                            }}
                            className="transition-all duration-200 focus:ring-2 focus:ring-blue-500"
                        />

                        {email && !isValidEmail && (
                            <p className="text-red-500 text-xs mt-2">
                                Please enter a valid email address
                            </p>
                        )}
                    </div>

                    <Button
                        title="Continue"
                        onClick={handleSubmit}
                        disabled={!isValidEmail}
                        className="
                            w-full
                            bg-blue-600
                            hover:bg-blue-700
                            transition-all
                            duration-200
                            disabled:opacity-50
                            disabled:cursor-not-allowed
                        "
                    />
                </div>
            </div>
        </div>
    );
}

export default MailPrompt;