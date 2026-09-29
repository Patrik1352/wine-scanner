<script setup lang="ts">
const props = defineProps<{ src: string | null; name: string }>()
const broken = ref(false)
watch(() => props.src, () => broken.value = false)
</script>
<template><img v-if="src && !broken" :src="src" :alt="name" @error="broken = true"><div v-else class="image-missing"><AppIcon name="glass" /><span>Изображение не добавлено</span></div></template>
