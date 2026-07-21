<script setup lang="ts">
import { computed, ref } from 'vue'
import { configApi } from '@anta/bridge'
import { Button, Card, DeviceSelect, Toggle } from '@anta/ui'
import { store } from '../store'

const micResult = ref<string | null>(null)
const micTesting = ref(false)
const ttsResult = ref<string | null>(null)
const ttsTesting = ref(false)

const voiceNames = computed<string[]>(() => {
  const v = store.voices
  if (!v) return []
  const oficiais = v.oficiais.map((o) => o.nome)
  const extras = v.instaladas.filter((n) => !oficiais.includes(n))
  return [...oficiais, ...extras]
})

async function testarMic() {
  micTesting.value = true
  micResult.value = null
  try {
    const r = await configApi.testMicrophone(store.form.mic_device, 2)
    micResult.value = r.ok
      ? `Nível captado: pico ${r.pico}, rms ${r.rms}. ${(r.pico ?? 0) < 0.01 ? '⚠ Muito baixo — fale mais perto?' : '✓ Ok'}`
      : `Falhou: ${r.msg}`
  } finally {
    micTesting.value = false
  }
}

async function testarTts() {
  ttsTesting.value = true
  ttsResult.value = null
  try {
    const r = await configApi.testTts(store.form.tts_voice, store.form.tts_output)
    ttsResult.value = r.ok ? '✓ Falou (ouviu?)' : `Falhou: ${r.msg}`
  } finally {
    ttsTesting.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <Card title="Microfone" subtitle="A ANTA guarda o NOME do device (sobrevive a troca de USB).">
      <div class="flex items-end gap-3">
        <div class="flex-1">
          <DeviceSelect
            v-model="store.form.mic_device"
            :options="store.microphones"
            label="Entrada de áudio"
          />
        </div>
        <Button variant="secondary" :disabled="micTesting" @click="testarMic">
          {{ micTesting ? 'Testando…' : 'Testar microfone' }}
        </Button>
      </div>
      <p v-if="micResult" class="mt-2 text-xs text-slate-500 dark:text-slate-400">{{ micResult }}</p>
    </Card>

    <Card title="Resposta por voz (TTS)" subtitle="Opcional: a ANTA fala as respostas (Piper, na CPU).">
      <Toggle v-model="store.form.tts" label="Falar as respostas" hint="Liga a síntese de voz local." />

      <div v-if="store.form.tts" class="mt-4 space-y-4 border-t border-slate-100 pt-4 dark:border-slate-800">
        <DeviceSelect
          v-model="store.form.tts_voice"
          :options="voiceNames"
          label="Voz"
          :placeholder="`padrão (${store.voices?.default ?? 'pt_BR'})`"
        />
        <div class="flex items-end gap-3">
          <div class="flex-1">
            <DeviceSelect
              v-model="store.form.tts_output"
              :options="store.speakers"
              label="Saída de áudio"
            />
          </div>
          <Button variant="secondary" :disabled="ttsTesting" @click="testarTts">
            {{ ttsTesting ? 'Falando…' : 'Testar voz' }}
          </Button>
        </div>
        <p v-if="ttsResult" class="text-xs text-slate-500 dark:text-slate-400">{{ ttsResult }}</p>
      </div>
    </Card>
  </div>
</template>
