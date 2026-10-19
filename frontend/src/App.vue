<script setup lang="ts">
import { RouterView } from 'vue-router';
import AdminShell from './layouts/AdminShell.vue';
</script>
<template><AdminShell><RouterView v-slot="{ Component,route }"><component :is="Component" :key="route.path"/></RouterView></AdminShell></template>
