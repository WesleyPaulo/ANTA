<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string }>()
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
    <header
      v-if="title || $slots.header"
      class="flex items-center justify-between border-b border-slate-100 px-5 py-3 dark:border-slate-800"
    >
      <div>
        <h2 v-if="title" class="text-sm font-semibold text-slate-900 dark:text-slate-100">{{ title }}</h2>
        <p v-if="subtitle" class="text-xs text-slate-500 dark:text-slate-400">{{ subtitle }}</p>
      </div>
      <slot name="header" />
    </header>
    <div class="p-5">
      <slot />
    </div>
  </section>
</template>
