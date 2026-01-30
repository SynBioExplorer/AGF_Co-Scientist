import React from 'react';
import { SettingsPanel } from '../components/settings/SettingsPanel';

export const SettingsPage: React.FC = () => {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Settings</h1>
      <div className="max-w-2xl">
        <SettingsPanel />
      </div>
    </div>
  );
};
