<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string, string> = {
 camera: 'M14 4h-4L8 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-4z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
 image: 'M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1 M3 16l6-6 5 5 3-3 4 4 M16 7h.01',
 arrow: 'M4 12h16m-6-6 6 6-6 6',
 scan: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M7 12h10',
 close: 'M6 6l12 12M6 18 18 6',
 check: 'M5 12l4 4L19 6',
 glass: 'M7 3h10l1 7a6 6 0 0 1-12 0z M12 16v6m-4 0h8M6 10h12',
 info: 'M12 8h.01M12 12v5 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
 leaf: 'M20 3C7 2 2 9 6 15s15 2 14-12z M4 21 16 9',
 retry: 'M3 10a9 9 0 1 1 1 8M3 4v6h6',
 shield: 'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6z M8 12l3 3 5-6',
 star: 'm12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3L12 17.5l-5.7 3 1.1-6.3L2.8 9.7l6.4-.9z'
}
</script>
<template><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.info" /></svg></template>
