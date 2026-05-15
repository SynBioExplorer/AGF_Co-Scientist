import * as React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { springSoft } from '../lib/motion';

export function CommandPalette(): React.ReactElement {
  const [open, setOpen] = React.useState(false);
  const navigate = useNavigate();

  React.useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function go(path: string): void {
    setOpen(false);
    navigate(path);
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: -10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: -6 }}
                transition={springSoft}
                className="fixed left-1/2 top-[20%] z-50 w-[min(640px,92vw)] -translate-x-1/2 overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-2xl dark:border-neutral-800 dark:bg-neutral-900"
                role="dialog"
                aria-label="Command palette"
                data-testid="command-palette"
              >
                <Dialog.Title className="sr-only">Command palette</Dialog.Title>
                <Command>
                  <Command.Input
                    placeholder="Type a command or search…"
                    className="w-full border-b border-neutral-200 bg-transparent px-4 py-3 text-sm outline-none placeholder:text-neutral-400 dark:border-neutral-800"
                  />
                  <Command.List className="max-h-72 overflow-y-auto p-2">
                    <Command.Empty className="px-3 py-6 text-center text-sm text-neutral-500">
                      No results.
                    </Command.Empty>
                    <Command.Group heading="Navigate">
                      <Command.Item
                        onSelect={() => go('/')}
                        className="cursor-pointer rounded-lg px-3 py-2 text-sm aria-selected:bg-sky-50 dark:aria-selected:bg-sky-900/30"
                      >
                        Dashboard
                      </Command.Item>
                      <Command.Item
                        onSelect={() => go('/settings')}
                        className="cursor-pointer rounded-lg px-3 py-2 text-sm aria-selected:bg-sky-50 dark:aria-selected:bg-sky-900/30"
                      >
                        Settings
                      </Command.Item>
                      <Command.Item
                        onSelect={() => go('/onboarding')}
                        className="cursor-pointer rounded-lg px-3 py-2 text-sm aria-selected:bg-sky-50 dark:aria-selected:bg-sky-900/30"
                      >
                        Re-run onboarding
                      </Command.Item>
                    </Command.Group>
                  </Command.List>
                </Command>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}
