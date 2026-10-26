import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../shared/api/client';
import { context } from '../shared/api/http';
import type { Session } from '../shared/types/domain';
interface Auth {
  session: Session | undefined;
  loading: boolean;
  expired: boolean;
  setSession: (s: Session) => Promise<void>;
  changeCompany: (id: string) => Promise<void>;
  logout: () => Promise<void>;
}
const AuthContext = createContext<Auth | null>(null);
const channel =
  typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('flow-company-context') : null;
export function SessionProvider({ children }: { children: ReactNode }) {
  const query = useQueryClient(),
    [expired, setExpired] = useState(false),
    [switching, setSwitching] = useState(false);
  const s = useQuery({
    queryKey: ['session'],
    queryFn: async () => {
      const s = await api.session();
      context.set(s);
      return s;
    },
    retry: false,
    staleTime: 60000,
  });
  const setSession = async (session: Session) => {
    setSwitching(true);
    context.reset();
    await query.cancelQueries();
    query.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
    context.set(session);
    setExpired(false);
    query.setQueryData(['session'], session);
    channel?.postMessage({ type: 'session-changed' });
    setSwitching(false);
  };
  const changeCompany = async (id: string) => {
    const session = await api.selectCompany(id);
    setSwitching(true);
    context.reset();
    await query.cancelQueries();
    query.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
    context.set(session);
    query.setQueryData(['session'], session);
    channel?.postMessage({ type: 'company-changed' });
    setSwitching(false);
  };
  useEffect(() => {
    const expire = () => {
      setExpired(true);
      void query.cancelQueries();
    };
    const receive = () => {
      setSwitching(true);
      context.reset();
      void query.cancelQueries().then(() => {
        query.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
        query.setQueryData(['session'], null);
        void query.refetchQueries({ queryKey: ['session'] }).finally(() => setSwitching(false));
      });
    };
    window.addEventListener('session-expired', expire);
    if (channel) channel.onmessage = receive;
    return () => {
      window.removeEventListener('session-expired', expire);
      if (channel) channel.onmessage = null;
    };
  }, [query]);
  return (
    <AuthContext.Provider
      value={{
        session: s.data,
        loading: s.isPending || switching,
        expired,
        setSession,
        changeCompany,
        logout: async () => {
          await api.logout();
          context.reset();
          await query.cancelQueries();
          query.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
          query.setQueryData(['session'], null);
          channel?.postMessage({ type: 'session-changed' });
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useSession() {
  const s = useContext(AuthContext);
  if (!s) throw new Error('SessionProvider missing');
  return s;
}
