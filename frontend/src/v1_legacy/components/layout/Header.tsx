import React from 'react';

export const Header: React.FC = () => {
  return (
    <header className="bg-indigo-600 text-white shadow-lg">
      <div className="container mx-auto px-4 py-4">
        <h1 className="text-2xl font-bold">AI Co-Scientist</h1>
        <p className="text-sm text-indigo-100">Multi-Agent Hypothesis Generation System</p>
      </div>
    </header>
  );
};
