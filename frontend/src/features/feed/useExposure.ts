import { useEffect, useRef } from 'react';
import { api } from '../../shared/api/client';
export function useExposure(itemId: string) {
  const ref = useRef<HTMLElement | null>(null),
    exposureId = useRef(crypto.randomUUID()),
    sent = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        clearTimeout(timer);
        if (entries[0]?.intersectionRatio >= 0.5 && !sent.current)
          timer = setTimeout(() => {
            sent.current = true;
            void api.exposure(itemId, 'VIEW', exposureId.current).catch(() => {});
          }, 1000);
      },
      { threshold: [0, 0.5, 1] },
    );
    observer.observe(el);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [itemId]);
  return {
    ref,
    click: () => {
      void api.exposure(itemId, 'CLICK', exposureId.current).catch(() => {});
    },
  };
}
