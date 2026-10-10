package dev.auspex.corehub.kafka;

/** A connectivity check for a store the listeners write to. Throwing counts as down. */
public interface StoreProbe {

    String name();

    boolean isUp();
}
