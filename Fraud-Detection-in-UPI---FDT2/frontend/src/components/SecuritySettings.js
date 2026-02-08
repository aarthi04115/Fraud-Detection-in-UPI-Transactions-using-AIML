import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from './NotificationSystem';
import api from '../api';

const SecuritySettings = ({ user }) => {
  const navigate = useNavigate();
  const { addNotification } = useNotifications();
  const [transactionLimit, setTransactionLimit] = useState(10000);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [initialLimit, setInitialLimit] = useState(10000);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);

  useEffect(() => {
    loadTransactionLimit();
  }, []);

  const loadTransactionLimit = async () => {
    try {
      setLoading(true);
      // Fetch current transaction limit from backend
      const response = await api.get('/api/user/transaction-limit');
      console.log('Loaded limit response:', response.data);
      const limit = response.data.daily_limit || 10000;
      setTransactionLimit(limit);
      setInitialLimit(limit);
    } catch (error) {
      console.error('Failed to load transaction limit:', error);
      addNotification({
        type: 'error',
        title: 'Load Failed',
        message: 'Failed to load transaction limit. Using default value.',
        category: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (transactionLimit <= 0) {
      addNotification({
        type: 'error',
        title: 'Invalid Limit',
        message: 'Transaction limit must be greater than 0.',
        category: 'error'
      });
      return;
    }

    setSaving(true);
    try {
      console.log('Saving limit:', transactionLimit);
      const response = await api.post('/api/user/transaction-limit', {
        daily_limit: transactionLimit
      });
      
      console.log('Save response:', response.data);
      setInitialLimit(transactionLimit);
      
      // Show success animation
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      
      addNotification({
        type: 'success',
        title: 'Limit Updated',
        message: `Your daily transaction limit has been set to ₹${transactionLimit.toLocaleString('en-IN')}.`,
        category: 'success'
      });
    } catch (error) {
      console.error('Failed to save transaction limit:', error);
      console.error('Error response:', error.response?.data);
      addNotification({
        type: 'error',
        title: 'Save Failed',
        message: error.response?.data?.detail || 'Unable to save transaction limit. Please try again.',
        category: 'error'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setTransactionLimit(initialLimit);
    
    // Show reset animation
    setResetSuccess(true);
    setTimeout(() => setResetSuccess(false), 1500);
    
    addNotification({
      type: 'info',
      title: 'Reset',
      message: 'Transaction limit reset to previous value.',
      category: 'default'
    });
  };

  const hasChanges = transactionLimit !== initialLimit;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 pb-20">
      {/* Animated background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute top-0 left-0 w-96 h-96 bg-purple-500 rounded-full filter blur-3xl opacity-20 animate-pulse"></div>
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-indigo-500 rounded-full filter blur-3xl opacity-20 animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-pink-500 rounded-full filter blur-3xl opacity-10 animate-pulse delay-500"></div>
      </div>

      {/* Header */}
      <div className="bg-black/20 backdrop-blur-xl border-b border-white/10 text-white p-6 pb-8">
        <div className="flex items-center mb-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="mr-4 text-purple-300 hover:text-white transition-colors"
            data-testid="back-button"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold">Set Transaction Limit</h1>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 -mt-4">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white/10 backdrop-blur-xl rounded-2xl shadow-xl p-8 border border-white/20">
            {/* User Info */}
            <div className="mb-8 pb-6 border-b border-white/10">
              <p className="text-purple-300 text-sm mb-2">Account</p>
              <h2 className="text-2xl font-bold text-white">{user?.name || 'User'}</h2>
              <p className="text-purple-400 text-sm mt-2">Phone: {user?.phone || 'N/A'}</p>
            </div>

            {/* Transaction Limit Setting */}
            <div className="space-y-6">
              <div>
                <label className="block text-white text-lg font-semibold mb-4">
                  <svg className="w-6 h-6 inline mr-2 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Daily Transaction Limit
                </label>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-3xl font-bold text-white">₹</span>
                    <input
                      type="number"
                      value={transactionLimit}
                      onChange={(e) => setTransactionLimit(parseInt(e.target.value) || 0)}
                      className="flex-1 bg-white/20 border border-white/30 rounded-xl px-6 py-4 text-2xl font-semibold text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:bg-white/25 transition-all"
                      min="1"
                    />
                  </div>
                  
                  <p className="text-white/60 text-sm">
                    Transactions exceeding this limit will require additional verification.
                  </p>

                  {/* Slider for quick adjustment */}
                  <div className="pt-4">
                    <input
                      type="range"
                      min="1000"
                      max="100000"
                      step="1000"
                      value={transactionLimit}
                      onChange={(e) => setTransactionLimit(parseInt(e.target.value))}
                      className="w-full h-2 bg-white/20 rounded-lg appearance-none cursor-pointer"
                      style={{
                        background: `linear-gradient(to right, rgb(120 53 255) 0%, rgb(120 53 255) ${(transactionLimit - 1000) / (100000 - 1000) * 100}%, rgb(255 255 255 / 0.2) ${(transactionLimit - 1000) / (100000 - 1000) * 100}%, rgb(255 255 255 / 0.2) 100%)`
                      }}
                    />
                    <div className="flex justify-between text-white/50 text-xs mt-2">
                      <span>₹1,000</span>
                      <span>₹100,000</span>
                    </div>
                  </div>

                  {/* Preset buttons */}
                  <div className="grid grid-cols-3 gap-2 pt-4">
                    {[10000, 25000, 50000].map((amount) => (
                      <button
                        key={amount}
                        onClick={() => setTransactionLimit(amount)}
                        className={`py-2 px-3 rounded-lg font-semibold transition-all duration-200 ${
                          transactionLimit === amount
                            ? 'bg-purple-600 text-white'
                            : 'bg-white/10 text-white/70 hover:bg-white/20'
                        }`}
                      >
                        ₹{(amount / 1000).toFixed(0)}K
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                <p className="text-blue-200 text-sm">
                  <svg className="w-4 h-4 inline mr-2 mb-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  This limit is tied to your account ({user?.phone}). All transactions within this limit will be monitored by our fraud detection system.
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 mt-8 pt-6 border-t border-white/10">
              <button
                onClick={handleReset}
                disabled={!hasChanges || saving}
                className={`flex-1 py-3 px-6 rounded-xl font-semibold transition-all duration-200 flex items-center justify-center relative overflow-hidden ${
                  hasChanges
                    ? 'bg-gray-600 text-white hover:bg-gray-700'
                    : 'bg-gray-600/50 text-gray-400 cursor-not-allowed'
                }`}
              >
                {resetSuccess && (
                  <div className="absolute inset-0 bg-green-500/30 animate-pulse flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Reset
              </button>
              
              <button
                onClick={handleSave}
                disabled={!hasChanges || saving}
                className={`flex-1 py-3 px-6 rounded-xl font-semibold transition-all duration-200 transform flex items-center justify-center relative overflow-hidden ${
                  hasChanges
                    ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-600 hover:to-orange-700 hover:scale-105 active:scale-95'
                    : 'bg-amber-500/50 text-amber-200/50 cursor-not-allowed'
                }`}
              >
                {saving && (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                )}
                
                {saveSuccess && !saving && (
                  <div className="absolute inset-0 bg-green-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
                
                {!saving && !saveSuccess && (
                  <>
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-6 2l4-4m0 0l4 4" />
                    </svg>
                    Save Limit
                  </>
                )}
                
                {saving && (
                  <span>Saving...</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SecuritySettings;
