import * as React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  useLocation,
  Navigate,
} from 'react-router-dom';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';

import { Toaster } from './components/Toaster';
import { CommandPalette } from './components/CommandPalette';
import { pageVariants, springSoft } from './lib/motion';
import { useSetupStatus } from './hooks/useSetupStatus';
import { useTheme } from './hooks/useTheme';

import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import Run from './pages/Run';
import Results from './pages/Results';
import Settings from './pages/Settings';

function AnimatedRoutes(): React.ReactElement {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
      >
        <Routes location={location}>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/run/:id" element={<Run />} />
          <Route path="/run/:id/results" element={<Results />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function SetupGate({ children }: { children: React.ReactNode }): React.ReactElement {
  const { status, loading } = useSetupStatus();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="mono text-xs text-neutral-500"
        >
          Loading…
        </motion.div>
      </div>
    );
  }
  if (status && !status.completed && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  return <>{children}</>;
}

export default function App(): React.ReactElement {
  // Initialize theme on mount.
  useTheme();

  return (
    <MotionConfig transition={springSoft}>
      <BrowserRouter>
        <SetupGate>
          <CommandPalette />
          <AnimatedRoutes />
          <Toaster />
        </SetupGate>
      </BrowserRouter>
    </MotionConfig>
  );
}
