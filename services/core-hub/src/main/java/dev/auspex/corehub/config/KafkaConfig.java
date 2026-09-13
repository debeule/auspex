package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.auspex.corehub.kafka.UnknownMajorVersionException;
import dev.auspex.corehub.model.ResearchSignalEvent;
import org.apache.kafka.common.serialization.ByteArraySerializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaOperations;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.support.serializer.ErrorHandlingDeserializer;
import org.springframework.kafka.support.serializer.JsonDeserializer;
import org.springframework.kafka.support.serializer.JsonSerializer;
import org.springframework.util.backoff.FixedBackOff;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.apache.kafka.clients.consumer.ConsumerConfig.*;
import static org.apache.kafka.clients.producer.ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG;
import static org.apache.kafka.clients.producer.ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG;

@Configuration
class KafkaConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Bean
    ConsumerFactory<String, ResearchSignalEvent> signalConsumerFactory(ObjectMapper objectMapper) {
        JsonDeserializer<ResearchSignalEvent> jsonDeser =
                new JsonDeserializer<>(ResearchSignalEvent.class, objectMapper);
        jsonDeser.setUseTypeHeaders(false);

        ErrorHandlingDeserializer<ResearchSignalEvent> valueDeser =
                new ErrorHandlingDeserializer<>(jsonDeser);

        return new DefaultKafkaConsumerFactory<>(
                consumerProps("corehub-signal"),
                new StringDeserializer(),
                valueDeser
        );
    }

    @Bean
    ConcurrentKafkaListenerContainerFactory<String, ResearchSignalEvent> signalListenerContainerFactory(
            ConsumerFactory<String, ResearchSignalEvent> signalConsumerFactory,
            DefaultErrorHandler signalErrorHandler
    ) {
        var factory = new ConcurrentKafkaListenerContainerFactory<String, ResearchSignalEvent>();
        factory.setConsumerFactory(signalConsumerFactory);
        factory.setCommonErrorHandler(signalErrorHandler);
        return factory;
    }

    @Bean
    ConsumerFactory<String, String> rawConsumerFactory() {
        ErrorHandlingDeserializer<String> valueDeser =
                new ErrorHandlingDeserializer<>(new StringDeserializer());
        return new DefaultKafkaConsumerFactory<>(
                consumerProps("corehub-raw"),
                new StringDeserializer(),
                valueDeser
        );
    }

    @Bean
    ConcurrentKafkaListenerContainerFactory<String, String> rawListenerContainerFactory(
            ConsumerFactory<String, String> rawConsumerFactory,
            DefaultErrorHandler rawErrorHandler
    ) {
        var factory = new ConcurrentKafkaListenerContainerFactory<String, String>();
        factory.setConsumerFactory(rawConsumerFactory);
        factory.setCommonErrorHandler(rawErrorHandler);
        return factory;
    }

    @Bean
    DefaultErrorHandler signalErrorHandler(
            DeadLetterPublishingRecoverer signalDltRecoverer
    ) {
        DefaultErrorHandler handler = new DefaultErrorHandler(signalDltRecoverer, new FixedBackOff(1000L, 2));
        handler.addNotRetryableExceptions(UnknownMajorVersionException.class);
        return handler;
    }

    @Bean
    DefaultErrorHandler rawErrorHandler(
            DeadLetterPublishingRecoverer rawDltRecoverer
    ) {
        return new DefaultErrorHandler(rawDltRecoverer, new FixedBackOff(1000L, 2));
    }

    /**
     * Routes to lowercase .dlt and partition -1 (producer chooses).
     * Default resolver gives uppercase .DLT and same partition — both wrong for us.
     * Re-verified against Spring Kafka 4.1 — see DECISIONS.md.
     *
     * Two templates handle the two DLT failure modes:
     *  byte[].class  → deserialization failures: DLPR extracts raw bytes from EHD headers
     *  Object.class  → processing failures (e.g. Neo4j throw, UnknownMajorVersionException):
     *                  value is the deserialized Java record, re-serialized as JSON
     */
    @Bean
    DeadLetterPublishingRecoverer signalDltRecoverer(
            @Qualifier("dltBytesKafkaTemplate") KafkaTemplate<Object, Object> bytesTemplate,
            @Qualifier("dltJsonKafkaTemplate")  KafkaTemplate<Object, Object> jsonTemplate
    ) {
        var templates = new LinkedHashMap<Class<?>, KafkaOperations<?, ?>>();
        templates.put(byte[].class, bytesTemplate);
        templates.put(Object.class,  jsonTemplate);
        return new DeadLetterPublishingRecoverer(templates,
                (record, ex) -> new org.apache.kafka.common.TopicPartition(
                        record.topic() + ".dlt", -1));
    }

    @Bean
    DeadLetterPublishingRecoverer rawDltRecoverer(
            @Qualifier("dltBytesKafkaTemplate") KafkaTemplate<Object, Object> bytesTemplate,
            @Qualifier("dltJsonKafkaTemplate")  KafkaTemplate<Object, Object> jsonTemplate
    ) {
        var templates = new LinkedHashMap<Class<?>, KafkaOperations<?, ?>>();
        templates.put(byte[].class, bytesTemplate);
        templates.put(Object.class,  jsonTemplate);
        return new DeadLetterPublishingRecoverer(templates,
                (record, ex) -> new org.apache.kafka.common.TopicPartition(
                        record.topic() + ".dlt", -1));
    }

    @Bean
    @Primary
    ProducerFactory<Object, Object> kafkaProducerFactory() {
        return new DefaultKafkaProducerFactory<>(Map.of(
                BOOTSTRAP_SERVERS_CONFIG, bootstrapServers,
                KEY_SERIALIZER_CLASS_CONFIG,   StringSerializer.class,
                VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class
        ));
    }

    @Bean
    @Primary
    KafkaTemplate<Object, Object> kafkaTemplate(
            @Qualifier("kafkaProducerFactory") ProducerFactory<Object, Object> kafkaProducerFactory
    ) {
        return new KafkaTemplate<>(kafkaProducerFactory);
    }

    @Bean
    ProducerFactory<Object, Object> dltBytesProducerFactory() {
        return new DefaultKafkaProducerFactory<>(Map.of(
                BOOTSTRAP_SERVERS_CONFIG, bootstrapServers,
                KEY_SERIALIZER_CLASS_CONFIG,   StringSerializer.class,
                VALUE_SERIALIZER_CLASS_CONFIG, ByteArraySerializer.class
        ));
    }

    @Bean
    KafkaTemplate<Object, Object> dltBytesKafkaTemplate(
            @Qualifier("dltBytesProducerFactory") ProducerFactory<Object, Object> dltBytesProducerFactory
    ) {
        return new KafkaTemplate<>(dltBytesProducerFactory);
    }

    @Bean
    ProducerFactory<Object, Object> dltJsonProducerFactory() {
        return new DefaultKafkaProducerFactory<>(Map.of(
                BOOTSTRAP_SERVERS_CONFIG, bootstrapServers,
                KEY_SERIALIZER_CLASS_CONFIG,   StringSerializer.class,
                VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class
        ));
    }

    @Bean
    KafkaTemplate<Object, Object> dltJsonKafkaTemplate(
            @Qualifier("dltJsonProducerFactory") ProducerFactory<Object, Object> dltJsonProducerFactory
    ) {
        return new KafkaTemplate<>(dltJsonProducerFactory);
    }

    @Bean
    KafkaTemplate<Object, Object> corroboratedKafkaTemplate(
            @Qualifier("dltJsonProducerFactory") ProducerFactory<Object, Object> dltJsonProducerFactory
    ) {
        return new KafkaTemplate<>(dltJsonProducerFactory);
    }

    private Map<String, Object> consumerProps(String groupId) {
        return Map.of(
                BOOTSTRAP_SERVERS_CONFIG, bootstrapServers,
                GROUP_ID_CONFIG, groupId,
                AUTO_OFFSET_RESET_CONFIG, "earliest",
                MAX_POLL_RECORDS_CONFIG, 50,
                ENABLE_AUTO_COMMIT_CONFIG, false
        );
    }
}
