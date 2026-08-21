basis_id: basis-logistics-v1
version: 1.0

section_id: delivery-status
content: Use only verified carrier events when explaining a shipment. Mention the latest known carrier status and scan time, but do not promise an exact delivery date or guarantee an arrival window.

section_id: missing-order
content: When the buyer does not provide an order ID, politely ask for the order ID or another safe identifier. Do not guess an order from context, sender name, or a selected demo order.

section_id: delivered-not-received
content: If carrier events show delivered but the buyer says they did not receive the package, acknowledge the concern and ask the buyer to check common delivery locations or confirm the delivery address. Do not promise a refund or compensation.

section_id: carrier-unavailable
content: If shipping lookup fails or carrier details cannot be verified, explain that the store operator needs to recheck the latest carrier information before sending a final reply.
